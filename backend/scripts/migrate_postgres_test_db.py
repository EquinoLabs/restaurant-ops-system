"""
ROMS Platform Governance — Isolated Test Database Migration Runner (OP-02)

Applies verified Alembic migrations strictly up to head 0014_add_missing_tenant_indexes
against an isolated, verified PostgreSQL test database.

Usage (Stage C when explicitly authorized):
    python scripts/migrate_postgres_test_db.py --confirm

Security & Isolation Rules:
- Requires --confirm flag.
- Target URL is read exclusively from ROMS_POSTGRES_TEST_DATABASE_URL.
- Never falls back to application DATABASE_URL, Settings, or .env.
- Injects a pre-verified SQLAlchemy connection directly into Alembic's programmatic context,
  bypassing Alembic env.py's application-URL resolution.
- Validates the migration DAG before execution.
- Verifies target identity and confirms roms_disposable_test_marker before running migrations.
- Confirms post-upgrade revision state and catalog constraints.
- Universal credential sanitization across all diagnostic and error outputs.
"""

import sys
import argparse
import os
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import text

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.postgres_guard import (
    validate_postgres_test_url,
    verify_migration_dag_head,
    verify_disposable_test_target,
    sanitize_error_message,
    EXPECTED_MIGRATION_HEAD,
    PostgresGuardError,
    ConfigurationError,
    TargetVerificationRefusal,
    MigrationGraphError,
)


def run_isolated_test_migration(
    raw_url: Optional[str],
    confirmation: bool = False,
    alembic_ini_path: str = "alembic.ini",
    expected_run_id: Optional[str] = None,
) -> str:
    """
    Programmatic execution of isolated test migrations.
    Injects a live verified connection directly into Alembic's programmatic runner.
    """
    if not confirmation:
        raise TargetVerificationRefusal(
            "Migration refusal: You must provide explicit confirmation (--confirm) "
            "to execute migrations against the test database."
        )

    # 1. Parse and validate test target URL (Strict isolation, zero fallback)
    target = validate_postgres_test_url(raw_url, expected_run_id=expected_run_id)

    # 2. Read-only inspection of migration DAG
    verify_migration_dag_head(alembic_ini_path=alembic_ini_path, expected_head=EXPECTED_MIGRATION_HEAD)

    # 3. Locate alembic.ini and script directory
    resolved_ini = alembic_ini_path
    if not os.path.exists(resolved_ini):
        alt = os.path.join("backend", alembic_ini_path)
        if os.path.exists(alt):
            resolved_ini = alt
        else:
            raise MigrationGraphError(f"Alembic config '{alembic_ini_path}' not found.")

    from alembic.config import Config
    from alembic import command
    cfg = Config(resolved_ini)

    candidates = [
        "alembic",
        os.path.join("backend", "alembic"),
        os.path.join(os.path.dirname(os.path.abspath(resolved_ini)), "alembic"),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isdir(os.path.join(c, "versions")):
            cfg.set_main_option("script_location", os.path.abspath(c))
            break

    # 4. Connect to target and perform safety verification
    engine = sa.create_engine(target.raw_url)
    try:
        with engine.connect() as connection:
            # Positive target verification (verifies marker table and zero non-test data)
            verify_disposable_test_target(connection, target)

            # Pre-upgrade revision check
            version_table_exists = connection.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'alembic_version'
            """)).scalar() or 0

            if version_table_exists > 0:
                current_rev = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if current_rev == EXPECTED_MIGRATION_HEAD:
                    return f"already_at_head:{EXPECTED_MIGRATION_HEAD}"

            # 5. Programmatic migration execution with injected connection
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, EXPECTED_MIGRATION_HEAD)

            # 6. Post-upgrade revision verification
            post_rev = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if post_rev != EXPECTED_MIGRATION_HEAD:
                raise TargetVerificationRefusal(
                    f"Post-migration verification failed: Expected revision '{EXPECTED_MIGRATION_HEAD}', "
                    f"but database reports '{post_rev}'."
                )

            # 7. Post-upgrade catalog constraints verification
            check_con = connection.execute(text("""
                SELECT COUNT(*) FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'users' AND c.conname = 'ck_users_platform_role_consistency'
            """)).scalar() or 0
            if check_con == 0:
                raise TargetVerificationRefusal(
                    "Post-migration catalog check failed: Missing constraint 'ck_users_platform_role_consistency'."
                )

            partial_idx = connection.execute(text("""
                SELECT COUNT(*) FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                WHERE t.relname = 'users' AND i.relname = 'ix_users_single_active_platform_owner'
            """)).scalar() or 0
            if partial_idx == 0:
                raise TargetVerificationRefusal(
                    "Post-migration catalog check failed: Missing partial unique index 'ix_users_single_active_platform_owner'."
                )

            return f"upgraded_to:{EXPECTED_MIGRATION_HEAD}"

    except PostgresGuardError:
        raise
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), target)
        raise TargetVerificationRefusal(f"Migration runner encountered an error and failed closed: {safe_msg}") from None
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Isolated migration runner for verified ROMS PostgreSQL test databases."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Explicit confirmation to execute migrations against the verified test database.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Expected provisioning run ID (defaults to ROMS_POSTGRES_TEST_RUN_ID env var).",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("[ERROR] Refusal: You must provide --confirm to execute test database migrations.")
        sys.exit(1)

    url = os.environ.get("ROMS_POSTGRES_TEST_DATABASE_URL")
    try:
        outcome = run_isolated_test_migration(
            raw_url=url, confirmation=True, expected_run_id=args.run_id
        )
        print(f"[SUCCESS] Test database migration completed: {outcome}")
    except (ConfigurationError, TargetVerificationRefusal, MigrationGraphError) as exc:
        print(f"[REFUSAL] {exc}")
        sys.exit(1)
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc))
        print(f"[FATAL] Migration aborted: {safe_msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
