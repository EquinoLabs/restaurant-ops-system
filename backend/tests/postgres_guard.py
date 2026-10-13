"""
ROMS Platform Governance — PostgreSQL Integration Test Execution Guards (OP-02)

Provides fail-closed, multi-layered execution guards and target identity verification
for PostgreSQL integration and concurrency testing.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional, List, Set
from urllib.parse import urlparse, urlunparse
import sqlalchemy as sa
from sqlalchemy import text


class PostgresGuardError(Exception):
    """Base exception for all PostgreSQL integration guard failures."""
    pass


class ConfigurationError(PostgresGuardError):
    """Raised when test database configuration is missing, malformed, or ambiguous."""
    pass


class TargetVerificationRefusal(PostgresGuardError):
    """Raised when the target database cannot be positively verified as an isolated, disposable test database."""
    pass


class MigrationGraphError(PostgresGuardError):
    """Raised when the Alembic migration graph does not match the expected linear head and continuity."""
    pass


@dataclass(frozen=True)
class ParsedPostgresTestTarget:
    raw_url: str
    redacted_url: str
    scheme: str
    username: Optional[str]
    host: str
    port: int
    database: str
    run_id: Optional[str] = None
    is_neon: bool = False


FORBIDDEN_NAME_TOKENS: Set[str] = {
    "prod", "production", "live", "main", "master", "staging", "stage"
}

EXPECTED_MIGRATION_HEAD: str = "0012_platform_role_constraints"
EXPECTED_ROOT_MIGRATION: str = "0001_initial_r1_schema"
HARNESS_MARKER_TABLE: str = "roms_disposable_test_marker"
HARNESS_MARKER_VERSION: str = "ROMS-OP02"
BOOTSTRAP_CONFIRMATION_TOKEN: str = "CONFIRM_INITIALIZE_EMPTY_TEST_DATABASE"

# Authorized Neon Safety Branch Target Configuration (OP-02)
NEON_EXPECTED_PROJECT_ID: str = "steep-hall-47922907"
NEON_EXPECTED_BRANCH_ID: str = "br-weathered-cherry-b34085w9"
NEON_FORBIDDEN_SOURCE_BRANCH_ID: str = "br-fancy-scene-b38p0d9u"
NEON_EXPECTED_ENDPOINT_ID: str = "ep-lucky-band-b3tbsmfz"
NEON_EXPECTED_DATABASE: str = "neondb"


def redact_dsn(dsn: Optional[str]) -> str:
    """
    Safely redacts passwords and credentials from PostgreSQL connection strings.
    Never exposes plaintext secrets in logs, exceptions, or reports.
    """
    if not dsn or not dsn.strip():
        return "<empty>"
    try:
        parsed = urlparse(dsn.strip())
        if parsed.password:
            masked_netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
            return urlunparse((parsed.scheme, masked_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        return dsn.strip()
    except Exception:
        return "postgresql+psycopg://****@<redacted>"


def sanitize_error_message(msg: Optional[str], target: Optional[ParsedPostgresTestTarget] = None) -> str:
    """
    Sanitizes arbitrary error messages to prevent credential leakage.
    Redacts any URI strings, strips known passwords or tokens, and normalizes output.
    """
    if not msg:
        return ""
    clean = str(msg)
    # Redact any URIs matching postgresql:// or postgresql+psycopg://
    clean = re.sub(
        r'(postgres(?:ql)?(?:\+psycopg(?:_async)?)?://)([^:]+):([^@]+)@',
        r'\1\2:****@',
        clean
    )
    # If a parsed target is provided and has a password, explicitly redact that password wherever it appears
    if target and target.username:
        try:
            parsed = urlparse(target.raw_url)
            if parsed.password and parsed.password in clean:
                clean = clean.replace(parsed.password, "****")
        except Exception:
            pass
    return clean


def validate_postgres_test_url(
    url: Optional[str],
    normal_app_url: Optional[str] = None,
    expected_run_id: Optional[str] = None,
) -> ParsedPostgresTestTarget:
    """
    Validates that the provided integration test database URL is present, correctly formatted,
    and strictly decoupled from the application runtime database.

    Fails closed on:
    - Missing or empty URL.
    - Matching application DATABASE_URL.
    - Invalid or unsupported driver schemes.
    - Missing host, port, or database name.
    - Inclusion of forbidden production/staging tokens in host or database name.
    """
    if not url or not url.strip():
        raise ConfigurationError(
            "ROMS_POSTGRES_TEST_DATABASE_URL is not set or empty. "
            "PostgreSQL integration tests require an explicit, dedicated test database URL."
        )

    clean_url = url.strip()
    redacted = redact_dsn(clean_url)

    # Decoupling check: Target must NOT match normal application database URL
    if normal_app_url and clean_url == normal_app_url.strip():
        raise ConfigurationError(
            f"Configuration refusal: ROMS_POSTGRES_TEST_DATABASE_URL ({redacted}) matches the "
            "application DATABASE_URL. Test execution is strictly forbidden against the application database."
        )

    env_db_url = os.environ.get("DATABASE_URL")
    if env_db_url and clean_url == env_db_url.strip():
        raise ConfigurationError(
            f"Configuration refusal: ROMS_POSTGRES_TEST_DATABASE_URL ({redacted}) matches "
            "the ambient DATABASE_URL environment variable. Execution aborted."
        )

    try:
        parsed = urlparse(clean_url)
    except Exception as exc:
        safe_exc = sanitize_error_message(str(exc))
        raise ConfigurationError(f"Malformed connection string: {safe_exc}") from None

    # Driver scheme validation
    raw_scheme = parsed.scheme.lower()
    if raw_scheme in ("postgres", "postgresql"):
        normalized_scheme = "postgresql+psycopg"
        clean_url = clean_url.replace(f"{parsed.scheme}://", f"{normalized_scheme}://", 1)
        redacted = redacted.replace(f"{parsed.scheme}://", f"{normalized_scheme}://", 1)
        parsed = urlparse(clean_url)
    elif raw_scheme in ("postgresql+psycopg", "postgresql+psycopg_async"):
        normalized_scheme = raw_scheme
    else:
        raise ConfigurationError(
            f"Unsupported database scheme '{raw_scheme}' in {redacted}. "
            "PostgreSQL integration tests require 'postgresql' or 'postgresql+psycopg'."
        )

    host = parsed.hostname or ""
    if not host:
        raise ConfigurationError(f"Missing host in connection URL: {redacted}")

    port = parsed.port or 5432
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise ConfigurationError(f"Missing database name in connection URL: {redacted}")

    # Forbidden keyword check (early safeguard layer)
    lower_db = db_name.lower()
    lower_host = host.lower()
    for token in FORBIDDEN_NAME_TOKENS:
        if token in lower_db or token in lower_host:
            raise ConfigurationError(
                f"Configuration refusal: Target ({redacted}) contains forbidden keyword '{token}'. "
                "Tests cannot target production or staging databases."
            )

    is_neon = "neon.tech" in host.lower()
    if is_neon:
        # Source branch protection: fail closed if forbidden source branch appears anywhere in URL
        if NEON_FORBIDDEN_SOURCE_BRANCH_ID.lower() in clean_url.lower():
            raise ConfigurationError(
                f"Configuration refusal: Target URL contains forbidden source branch "
                f"'{NEON_FORBIDDEN_SOURCE_BRANCH_ID}'. Test execution against the source branch is strictly forbidden."
            )

        # Direct endpoint normalization: strip -pooler to prevent connection pooler interference
        if "-pooler" in host.lower():
            direct_host = host.replace("-pooler", "")
            clean_url = clean_url.replace(host, direct_host)
            redacted = redacted.replace(host, direct_host)
            host = direct_host
            parsed = urlparse(clean_url)

        # Authorized endpoint check
        if not host.lower().startswith(NEON_EXPECTED_ENDPOINT_ID.lower()):
            raise ConfigurationError(
                f"Configuration refusal: Neon host '{host}' does not match authorized "
                f"endpoint '{NEON_EXPECTED_ENDPOINT_ID}'. Execution refused."
            )

        if db_name.lower() != NEON_EXPECTED_DATABASE.lower():
            raise ConfigurationError(
                f"Configuration refusal: Neon target database '{db_name}' does not match "
                f"expected database '{NEON_EXPECTED_DATABASE}'."
            )

    env_run_id = os.environ.get("ROMS_POSTGRES_TEST_RUN_ID")
    env_run_id = env_run_id.strip() if env_run_id and env_run_id.strip() else None

    clean_expected_run_id = expected_run_id.strip() if expected_run_id and expected_run_id.strip() else None

    # Mismatch check: fail closed if explicit argument contradicts environment variable
    if clean_expected_run_id and env_run_id and clean_expected_run_id != env_run_id:
        raise ConfigurationError(
            f"Configuration refusal: Explicit run ID '{clean_expected_run_id}' mismatches "
            f"ROMS_POSTGRES_TEST_RUN_ID environment variable '{env_run_id}'. "
            "Refusing execution with conflicting correlation identifiers."
        )

    resolved_run_id = clean_expected_run_id or env_run_id

    return ParsedPostgresTestTarget(
        raw_url=clean_url,
        redacted_url=redacted,
        scheme=normalized_scheme,
        username=parsed.username,
        host=host,
        port=port,
        database=db_name,
        run_id=resolved_run_id,
        is_neon=is_neon,
    )


def verify_migration_dag_head(
    alembic_ini_path: str = "alembic.ini",
    expected_head: str = EXPECTED_MIGRATION_HEAD
) -> None:
    """
    Read-only inspection of the Alembic migration directory.
    Verifies that the migration graph has exactly one head and matches the expected revision,
    with unbroken DAG continuity back to the root migration.
    Does NOT connect to any database or execute Alembic.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    # Locate alembic.ini if run from backend or repo root
    resolved_ini = alembic_ini_path
    if not os.path.exists(resolved_ini):
        alt_path = os.path.join("backend", alembic_ini_path)
        if os.path.exists(alt_path):
            resolved_ini = alt_path
        else:
            raise MigrationGraphError(f"Alembic configuration file '{alembic_ini_path}' not found.")

    cfg = Config(resolved_ini)
    # Dynamically resolve alembic script directory whether invoked from root or backend
    candidates = [
        "alembic",
        os.path.join("backend", "alembic"),
        os.path.join(os.path.dirname(os.path.abspath(resolved_ini)), "alembic"),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isdir(os.path.join(c, "versions")):
            cfg.set_main_option("script_location", os.path.abspath(c))
            break

    try:
        script = ScriptDirectory.from_config(cfg)
    except Exception as exc:
        raise MigrationGraphError(f"Failed to inspect Alembic migration directory: {exc}")

    heads = script.get_heads()
    if len(heads) != 1:
        raise MigrationGraphError(
            f"Alembic graph anomaly: Expected exactly 1 migration head, but found {len(heads)}: {heads}."
        )

    actual_head = heads[0]
    if actual_head != expected_head:
        raise MigrationGraphError(
            f"Alembic head mismatch: Expected migration head '{expected_head}', but found '{actual_head}'. "
            "Refusing execution until migration expectations are aligned."
        )

    # Verify DAG continuity from head down to root
    current = script.get_revision(actual_head)
    visited: List[str] = []
    while current is not None:
        visited.append(current.revision)
        if current.down_revision is None:
            break
        if isinstance(current.down_revision, (list, tuple)):
            if len(current.down_revision) != 1:
                raise MigrationGraphError(
                    f"Alembic branch merge detected at revision '{current.revision}': {current.down_revision}."
                )
            down_rev = current.down_revision[0]
        else:
            down_rev = current.down_revision
        current = script.get_revision(down_rev)

    if visited[-1] != EXPECTED_ROOT_MIGRATION:
        raise MigrationGraphError(
            f"Alembic root mismatch: Expected root '{EXPECTED_ROOT_MIGRATION}', but chain terminated at '{visited[-1]}'."
        )


def verify_neon_safety_branch_target(
    connection: sa.Connection,
    target: ParsedPostgresTestTarget
) -> None:
    """
    Positive target identity verification for the authorized Neon safety branch.
    Validates project, branch, and endpoint against PostgreSQL settings.
    Guarantees 100% isolation from the source branch and verifies schema head.
    """
    try:
        # 1. Database name check
        server_db = connection.execute(text("SELECT current_database()")).scalar()
        if not server_db or server_db.lower() != NEON_EXPECTED_DATABASE.lower():
            raise TargetVerificationRefusal(
                f"Target database identity mismatch: Connected to database '{server_db}', "
                f"expected '{NEON_EXPECTED_DATABASE}'. Aborting."
            )

        # 2. Neon-specific system settings verification
        project_id = connection.execute(text("SELECT current_setting('neon.project_id', true)")).scalar()
        if not project_id or str(project_id).strip() != NEON_EXPECTED_PROJECT_ID:
            raise TargetVerificationRefusal(
                f"Neon project identity mismatch: Connected to project '{project_id}', "
                f"expected '{NEON_EXPECTED_PROJECT_ID}'. Aborting."
            )

        branch_id = connection.execute(text("SELECT current_setting('neon.branch_id', true)")).scalar()
        if branch_id == NEON_FORBIDDEN_SOURCE_BRANCH_ID:
            raise TargetVerificationRefusal(
                f"CRITICAL SAFETY VIOLATION: Connected to forbidden source branch '{branch_id}'. "
                "Aborting immediately to protect production data."
            )
        if not branch_id or str(branch_id).strip() != NEON_EXPECTED_BRANCH_ID:
            raise TargetVerificationRefusal(
                f"Neon branch identity mismatch: Connected to branch '{branch_id}', "
                f"expected safety branch '{NEON_EXPECTED_BRANCH_ID}'. Aborting."
            )

        endpoint_id = connection.execute(text("SELECT current_setting('neon.endpoint_id', true)")).scalar()
        if not endpoint_id or str(endpoint_id).strip() != NEON_EXPECTED_ENDPOINT_ID:
            raise TargetVerificationRefusal(
                f"Neon endpoint identity mismatch: Connected to endpoint '{endpoint_id}', "
                f"expected '{NEON_EXPECTED_ENDPOINT_ID}'. Aborting."
            )

        # 3. Direct endpoint verification (ensure no pooler routing)
        if "-pooler" in target.host.lower():
            raise TargetVerificationRefusal(
                f"Target endpoint refusal: Host '{target.host}' is a pooled endpoint. "
                "Integration testing requires direct connection."
            )

        # 4. Public schema tables & Alembic revision check
        tables_res = connection.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)).scalars().all()
        tables_set = set(tables_res)

        if "alembic_version" not in tables_set:
            raise TargetVerificationRefusal(
                "Alembic version table missing on safety branch. Schema is unmigrated."
            )

        current_rev = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current_rev != EXPECTED_MIGRATION_HEAD:
            raise TargetVerificationRefusal(
                f"Alembic revision mismatch on safety branch: Found '{current_rev}', "
                f"expected head '{EXPECTED_MIGRATION_HEAD}'."
            )

        # 5. Pre-existing invariant check
        if "users" in tables_set:
            active_owners = connection.execute(text("""
                SELECT COUNT(*) FROM users WHERE platform_role = 'owner' AND status = 'active'
            """)).scalar() or 0
            if active_owners > 0:
                raise TargetVerificationRefusal(
                    f"Pre-condition refusal: Found {active_owners} active platform owner(s). "
                    "Safety branch must start with 0 active platform owners for clean concurrency tests."
                )

    except PostgresGuardError:
        raise
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), target)
        raise TargetVerificationRefusal(
            f"Neon target verification encountered an unexpected error and failed closed: {safe_msg}"
        ) from None


def verify_disposable_test_target(
    connection: sa.Connection,
    target: ParsedPostgresTestTarget
) -> None:
    """
    Performs positive target identity and safety verification against a live PostgreSQL connection
    during ordinary integration-test runs.

    Strict Principles:
    1. Normal test runs NEVER automatically initialize schemas or create markers.
    2. An empty database without a marker table is REFUSED (must be explicitly bootstrapped first).
    3. Tables without the marker table are REFUSED.
    4. Marker table must exist with valid marker_version and is_disposable=TRUE.
    5. Database must contain zero non-test business rows.
    6. Does not expose application row contents or raw credentials.
    7. All unexpected exceptions are sanitized and chained raw exceptions suppressed.
    """
    if target.is_neon:
        verify_neon_safety_branch_target(connection, target)
        return

    try:
        # 1. Verify active database name from PostgreSQL catalog
        server_db = connection.execute(text("SELECT current_database()")).scalar()
        if not server_db or server_db != target.database:
            raise TargetVerificationRefusal(
                f"Target database identity mismatch: Connected to database '{server_db}', "
                f"expected '{target.database}'. Aborting."
            )

        # 2. Loopback check for local configurations
        if target.host in ("localhost", "127.0.0.1", "::1"):
            server_addr = connection.execute(text("SELECT inet_server_addr()")).scalar()
            # In PostgreSQL, UNIX domain socket connections return NULL for inet_server_addr()
            if server_addr is not None:
                addr_str = str(server_addr)
                if addr_str not in ("127.0.0.1", "::1"):
                    raise TargetVerificationRefusal(
                        f"Host identity refusal: Target host was specified as local, but PostgreSQL server "
                        f"reports address '{addr_str}'. Aborting."
                    )

        # 3. Inspect public schema tables
        tables_res = connection.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)).scalars().all()
        tables_set = set(tables_res)

        # Case A: Fresh, empty database (0 public tables) -> REFUSE!
        # Normal integration test execution does NOT auto-initialize or auto-create markers!
        if len(tables_set) == 0:
            raise TargetVerificationRefusal(
                f"Refusal: Target database '{server_db}' is completely empty and uninitialized. "
                "Ordinary integration tests never auto-initialize schemas or create markers. "
                "Execute the explicit bootstrap procedure first before running tests."
            )

        # Case B: Tables exist but marker is missing -> REFUSE!
        if HARNESS_MARKER_TABLE not in tables_set:
            raise TargetVerificationRefusal(
                f"Refusal: Target database '{server_db}' contains {len(tables_set)} existing tables "
                f"but lacks the mandatory test marker table '{HARNESS_MARKER_TABLE}'. "
                "To prevent accidental data loss or mutation, the target must have been initialized "
                "via the explicit test bootstrap procedure."
            )

        # Case C: Marker table exists; verify its validity
        marker_row = connection.execute(text(f"""
            SELECT is_disposable, marker_version
            FROM {HARNESS_MARKER_TABLE}
            ORDER BY id DESC
            LIMIT 1
        """)).fetchone()

        if not marker_row or not marker_row[0] or marker_row[1] != HARNESS_MARKER_VERSION:
            raise TargetVerificationRefusal(
                f"Refusal: Test marker table in '{server_db}' is invalid or from an incompatible harness version."
            )

        # Target Run ID Verification (ties database connection to specific container and run)
        if target.run_id:
            server_run_id = connection.execute(text("SELECT current_setting('roms.run_id', true)")).scalar()
            if server_run_id != target.run_id:
                raise TargetVerificationRefusal(
                    f"Container identity mismatch: PostgreSQL server reports roms.run_id='{server_run_id}', "
                    f"expected '{target.run_id}'. Aborting."
                )

            marker_run_id = connection.execute(text(f"""
                SELECT run_id FROM {HARNESS_MARKER_TABLE} ORDER BY id DESC LIMIT 1
            """)).scalar()
            if marker_run_id != target.run_id:
                raise TargetVerificationRefusal(
                    f"Marker run ID mismatch: Test marker table reports run_id='{marker_run_id}', "
                    f"expected '{target.run_id}'. Aborting."
                )

        # Verify business table contents (if present) contain no non-test records
        # Count check only — never exposes row contents
        if "businesses" in tables_set:
            non_test_count = connection.execute(text("""
                SELECT COUNT(*) FROM businesses WHERE name NOT LIKE 'Test %'
            """)).scalar() or 0
            if non_test_count > 0:
                raise TargetVerificationRefusal(
                    f"Refusal: Target database '{server_db}' contains {non_test_count} unrecognized business record(s). "
                    "Refusing to execute against a database with non-test data."
                )

    except PostgresGuardError:
        raise
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), target)
        raise TargetVerificationRefusal(
            f"Target verification encountered an unexpected error and failed closed: {safe_msg}"
        ) from None


def bootstrap_disposable_test_database(
    connection: sa.Connection,
    target: ParsedPostgresTestTarget,
    confirmation_token: str
) -> str:
    """
    Explicit administrative initialization procedure for a newly provisioned test database.
    Must ONLY be executed via an explicit administrative command with confirmation_token.

    Strict Requirements:
    1. Confirmation token must match BOOTSTRAP_CONFIRMATION_TOKEN.
    2. Target database name from catalog must match target.database.
    3. Loopback requirement enforced for local configurations.
    4. Database must be completely and strictly empty (0 tables in public schema).
       If ANY table exists (even an old marker or partial schema), bootstrap REFUSES.
    5. Creates roms_disposable_test_marker with unique cluster GUID and timestamp.

    Returns the generated cluster GUID.
    Never exposes credentials or application contents.
    """
    if confirmation_token != BOOTSTRAP_CONFIRMATION_TOKEN:
        raise TargetVerificationRefusal(
            f"Bootstrap refusal: Invalid confirmation token '{confirmation_token}'. "
            f"Expected '{BOOTSTRAP_CONFIRMATION_TOKEN}'."
        )

    try:
        server_db = connection.execute(text("SELECT current_database()")).scalar()
        if not server_db or server_db != target.database:
            raise TargetVerificationRefusal(
                f"Target database identity mismatch: Connected to database '{server_db}', "
                f"expected '{target.database}'. Aborting bootstrap."
            )

        if target.host in ("localhost", "127.0.0.1", "::1"):
            server_addr = connection.execute(text("SELECT inet_server_addr()")).scalar()
            if server_addr is not None:
                addr_str = str(server_addr)
                if addr_str not in ("127.0.0.1", "::1"):
                    raise TargetVerificationRefusal(
                        f"Host identity refusal: Target host was specified as local, but PostgreSQL server "
                        f"reports address '{addr_str}'. Aborting bootstrap."
                    )

        # Port check: Must be a dedicated non-default test port (e.g. 5433)
        if target.port == 5432:
            raise TargetVerificationRefusal(
                "Port conflict refusal: Target is configured on default PostgreSQL port 5432. "
                "Bootstrap requires a dedicated, non-default test port (e.g. 5433) to prevent colliding "
                "with ambient local development or production databases."
            )

        # Role check: User must be a dedicated test user (not postgres or application user)
        server_user = connection.execute(text("SELECT current_user")).scalar()
        if not server_user or server_user != target.username:
            raise TargetVerificationRefusal(
                f"Target user identity mismatch: Connected as '{server_user}', expected '{target.username}'."
            )
        if server_user.lower() in ("postgres", "roms_user", "admin", "root"):
            raise TargetVerificationRefusal(
                f"User identity refusal: Username '{server_user}' is a standard or administrative role. "
                "Bootstrap requires a dedicated test role (e.g. 'roms_test_user')."
            )

        # Uptime check: Server must be newly launched (< 3600 seconds)
        uptime_seconds = connection.execute(text("""
            SELECT EXTRACT(EPOCH FROM (NOW() - pg_postmaster_start_time()))
        """)).scalar() or 0
        if uptime_seconds > 3600:
            raise TargetVerificationRefusal(
                f"Host identity refusal: PostgreSQL server has been running for {int(uptime_seconds)}s. "
                "Bootstrap requires a newly launched, ephemeral test container (< 3600s uptime). "
                "Refusing to execute against a pre-existing or long-running database instance."
            )

        # Inspect public schema tables: Must be strictly 0 tables
        tables_res = connection.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)).scalars().all()

        if len(tables_res) > 0:
            raise TargetVerificationRefusal(
                f"Bootstrap refusal: Target database '{server_db}' already contains {len(tables_res)} "
                "existing table(s). Bootstrap requires a strictly empty database to prevent overwriting "
                "or re-marking an existing database. Zero tables were modified."
            )


        # Target Run ID Verification (ties database connection to specific container and run)
        if target.run_id:
            server_run_id = connection.execute(text("SELECT current_setting('roms.run_id', true)")).scalar()
            if server_run_id != target.run_id:
                raise TargetVerificationRefusal(
                    f"Container identity mismatch: PostgreSQL server reports roms.run_id='{server_run_id}', "
                    f"expected '{target.run_id}'. Aborting bootstrap."
                )

        import uuid
        cluster_guid = f"roms-test-{uuid.uuid4().hex}"

        connection.execute(text(f"""
            CREATE TABLE {HARNESS_MARKER_TABLE} (
                id SERIAL PRIMARY KEY,
                marker_version VARCHAR(50) NOT NULL,
                cluster_guid VARCHAR(64) NOT NULL,
                run_id VARCHAR(64),
                is_disposable BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            INSERT INTO {HARNESS_MARKER_TABLE} (marker_version, cluster_guid, run_id, is_disposable)
            VALUES ('{HARNESS_MARKER_VERSION}', :guid, :run_id, TRUE);
        """), {"guid": cluster_guid, "run_id": target.run_id})

        return cluster_guid
    except PostgresGuardError:
        raise
    except Exception as exc:
        safe_msg = sanitize_error_message(str(exc), target)
        raise TargetVerificationRefusal(
            f"Bootstrap encountered an unexpected error and failed closed: {safe_msg}"
        ) from None
