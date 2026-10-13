"""
ROMS Platform Governance — Test Database Bootstrap CLI (OP-02)

Explicit administrative script to initialize a newly provisioned, strictly empty
PostgreSQL test database with the ROMS test suite marker table.

Usage (Stage C when authorized):
    python scripts/init_postgres_test_db.py --confirm-bootstrap

Security Rules:
- Requires ROMS_POSTGRES_TEST_DATABASE_URL to be set and verified.
- Target database must be completely empty (0 tables).
- Requires explicit CLI flag --confirm-bootstrap.
- Never runs automatically during normal test runs.
- Does not modify existing databases containing tables.
"""

import sys
import argparse
import os
import sqlalchemy as sa

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.postgres_guard import (
    validate_postgres_test_url,
    bootstrap_disposable_test_database,
    BOOTSTRAP_CONFIRMATION_TOKEN,
    ConfigurationError,
    TargetVerificationRefusal,
    sanitize_error_message,
)


def main():
    parser = argparse.ArgumentParser(
        description="Explicit bootstrap tool for newly provisioned ROMS PostgreSQL test databases."
    )
    parser.add_argument(
        "--confirm-bootstrap",
        action="store_true",
        default=False,
        help="Explicit confirmation to initialize a verified empty test database.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Expected provisioning run ID (defaults to ROMS_POSTGRES_TEST_RUN_ID env var).",
    )
    args = parser.parse_args()

    if not args.confirm_bootstrap:
        print("[ERROR] Refusal: You must provide --confirm-bootstrap to initialize a test database.")
        sys.exit(1)

    url = os.environ.get("ROMS_POSTGRES_TEST_DATABASE_URL")
    try:
        target = validate_postgres_test_url(url, expected_run_id=args.run_id)
    except ConfigurationError as exc:
        print(f"[ERROR] Configuration Refusal: {exc}")
        sys.exit(1)

    engine = sa.create_engine(target.raw_url)
    try:
        with engine.connect() as conn:
            with conn.begin():
                guid = bootstrap_disposable_test_database(
                    conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
                )
                print(f"[SUCCESS] Test database '{target.database}' positively verified empty and initialized.")
                print(f"[SUCCESS] Cluster GUID: {guid}")
    except TargetVerificationRefusal as exc:
        print(f"[REFUSAL] Bootstrap Aborted: {exc}")
        sys.exit(1)
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), target)
        print(f"[FATAL] Unexpected error during bootstrap: {safe_msg}")
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
