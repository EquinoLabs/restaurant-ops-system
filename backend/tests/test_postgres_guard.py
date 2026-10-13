"""
Unit Tests for ROMS PostgreSQL Integration Test Execution Guards (OP-02)

Validates all 6 guard layers, DSN redaction, error message sanitization,
fail-closed refusal behavior, empty-database bootstrap requirements,
and migration DAG head verification without connecting to any real database.
"""

import os
import pytest
from unittest.mock import MagicMock
from tests.postgres_guard import (
    redact_dsn,
    sanitize_error_message,
    validate_postgres_test_url,
    verify_migration_dag_head,
    verify_disposable_test_target,
    bootstrap_disposable_test_database,
    ParsedPostgresTestTarget,
    ConfigurationError,
    TargetVerificationRefusal,
    MigrationGraphError,
    EXPECTED_MIGRATION_HEAD,
    BOOTSTRAP_CONFIRMATION_TOKEN,
)


def test_redact_dsn():
    # Password present
    dsn = "postgresql+psycopg://myuser:supersecretpass@localhost:5432/roms_test"
    redacted = redact_dsn(dsn)
    assert "supersecretpass" not in redacted
    assert "myuser:****@localhost:5432/roms_test" in redacted

    # No password present
    dsn_no_pw = "postgresql+psycopg://myuser@localhost:5432/roms_test"
    assert redact_dsn(dsn_no_pw) == dsn_no_pw

    # Empty / None
    assert redact_dsn("") == "<empty>"
    assert redact_dsn(None) == "<empty>"


def test_sanitize_error_message():
    raw_err = (
        'OperationalError: connection to "postgresql+psycopg://myuser:supersecretpassword@127.0.0.1:5432/test_db" '
        'failed: password authentication failed for user "myuser"'
    )
    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://myuser:supersecretpassword@127.0.0.1:5432/test_db",
        redacted_url="postgresql+psycopg://myuser:****@127.0.0.1:5432/test_db",
        scheme="postgresql+psycopg",
        username="myuser",
        host="127.0.0.1",
        port=5432,
        database="test_db"
    )

    clean = sanitize_error_message(raw_err, target)
    assert "supersecretpassword" not in clean
    assert "myuser:****@127.0.0.1:5432/test_db" in clean

    # Direct password leakage test
    raw_pw_leak = "FATAL: password supersecretpassword rejected"
    clean_pw = sanitize_error_message(raw_pw_leak, target)
    assert "supersecretpassword" not in clean_pw
    assert "****" in clean_pw


def test_validate_postgres_test_url_fails_on_missing_or_empty():
    with pytest.raises(ConfigurationError, match="not set or empty"):
        validate_postgres_test_url(None)

    with pytest.raises(ConfigurationError, match="not set or empty"):
        validate_postgres_test_url("   ")


def test_validate_postgres_test_url_fails_on_app_url_collision(monkeypatch):
    app_url = "postgresql+psycopg://app_user:pass@localhost:5432/roms_app"
    test_url = "postgresql+psycopg://app_user:pass@localhost:5432/roms_app"

    with pytest.raises(ConfigurationError, match="matches the application DATABASE_URL"):
        validate_postgres_test_url(test_url, normal_app_url=app_url)

    # Also test via ambient environment variable
    monkeypatch.setenv("DATABASE_URL", app_url)
    with pytest.raises(ConfigurationError, match="matches the ambient DATABASE_URL"):
        validate_postgres_test_url(test_url)


def test_validate_postgres_test_url_fails_on_invalid_scheme():
    with pytest.raises(ConfigurationError, match="Unsupported database scheme 'sqlite'"):
        validate_postgres_test_url("sqlite:///:memory:")

    with pytest.raises(ConfigurationError, match="Unsupported database scheme 'mysql'"):
        validate_postgres_test_url("mysql://user:pass@localhost:3306/test_db")


def test_validate_postgres_test_url_fails_on_forbidden_tokens():
    forbidden_urls = [
        "postgresql+psycopg://user:pass@localhost:5432/roms_prod",
        "postgresql+psycopg://user:pass@localhost:5432/roms_staging_db",
        "postgresql+psycopg://user:pass@prod-cluster.internal:5432/roms_test",
        "postgresql+psycopg://user:pass@staging.neon.tech:5432/test_db",
    ]
    for bad_url in forbidden_urls:
        with pytest.raises(ConfigurationError, match="contains forbidden keyword"):
            validate_postgres_test_url(bad_url)


def test_validate_postgres_test_url_success():
    valid_url = "postgresql+psycopg://test_user:test_pass@localhost:5432/roms_test_db"
    target = validate_postgres_test_url(valid_url)
    assert target.database == "roms_test_db"
    assert target.host == "localhost"
    assert target.port == 5432
    assert target.username == "test_user"
    assert target.scheme == "postgresql+psycopg"
    assert "test_pass" not in target.redacted_url


def test_verify_migration_dag_head_actual_repository():
    # Points to actual alembic.ini in repository without database connection
    # Must succeed verifying the linear DAG head 0012_platform_role_constraints
    verify_migration_dag_head(
        alembic_ini_path="alembic.ini",
        expected_head=EXPECTED_MIGRATION_HEAD
    )


def test_verify_migration_dag_head_mismatch():
    with pytest.raises(MigrationGraphError, match="Alembic head mismatch"):
        verify_migration_dag_head(
            alembic_ini_path="alembic.ini",
            expected_head="0013_nonexistent_migration"
        )


def test_verify_disposable_test_target_refuses_empty_uninitialized_database():
    mock_conn = MagicMock()
    # 1. current_database() returns target db name
    # 2. inet_server_addr() returns 127.0.0.1
    # 3. public schema tables count is 0 (uninitialized)
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),  # current_database()
        MagicMock(scalar=lambda: "127.0.0.1"),      # inet_server_addr()
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # table names
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    # Must REFUSE because ordinary test runs never auto-initialize empty databases
    with pytest.raises(TargetVerificationRefusal, match="completely empty and uninitialized"):
        verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_succeeds_with_valid_marker_and_clean_data():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["users", "businesses", "roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),  # marker valid
        MagicMock(scalar=lambda: 0),  # 0 non-test business records
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    # Must pass cleanly
    verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_name_mismatch():
    mock_conn = MagicMock()
    mock_conn.execute.return_value = MagicMock(scalar=lambda: "production_db")

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="Target database identity mismatch"):
        verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_refuses_tables_without_marker():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["users", "businesses", "orders"])),
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="lacks the mandatory test marker table"):
        verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_refuses_when_non_test_data_present():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["users", "businesses", "roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),  # marker valid
        MagicMock(scalar=lambda: 5),  # 5 unrecognized business rows!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="unrecognized business record"):
        verify_disposable_test_target(mock_conn, target)


def test_bootstrap_disposable_test_database_success():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),   # current_database()
        MagicMock(scalar=lambda: "127.0.0.1"),       # inet_server_addr()
        MagicMock(scalar=lambda: "roms_test_user"),  # current_user
        MagicMock(scalar=lambda: 120),               # uptime_seconds (2 mins)
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # strictly 0 tables
        None,  # table creation execution
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db"
    )

    guid = bootstrap_disposable_test_database(
        mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
    )
    assert guid.startswith("roms-test-")


def test_bootstrap_disposable_test_database_refuses_port_5432():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5432/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5432/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5432,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="Port conflict refusal"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
        )


def test_bootstrap_disposable_test_database_refuses_standard_user():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalar=lambda: "postgres"),  # administrative user!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://postgres:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://postgres:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="postgres",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="User identity refusal"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
        )


def test_bootstrap_disposable_test_database_refuses_high_uptime():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalar=lambda: "roms_test_user"),
        MagicMock(scalar=lambda: 86400),  # 24 hours uptime!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="Host identity refusal: PostgreSQL server has been running for 86400s"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
        )


def test_bootstrap_disposable_test_database_refuses_non_empty_database():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalar=lambda: "roms_test_user"),
        MagicMock(scalar=lambda: 120),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["users", "businesses"])),  # existing tables
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="already contains 2 existing table"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
        )


def test_bootstrap_disposable_test_database_refuses_invalid_token():
    mock_conn = MagicMock()
    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db"
    )

    with pytest.raises(TargetVerificationRefusal, match="Invalid confirmation token"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token="wrong_token"
        )


def test_validate_postgres_test_url_resolves_run_id(monkeypatch):
    test_url = "postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db"

    # From explicit parameter
    target = validate_postgres_test_url(test_url, expected_run_id="run-12345")
    assert target.run_id == "run-12345"

    # From environment variable
    monkeypatch.setenv("ROMS_POSTGRES_TEST_RUN_ID", "run-env-67890")
    target_env = validate_postgres_test_url(test_url)
    assert target_env.run_id == "run-env-67890"


def test_bootstrap_disposable_test_database_with_matching_run_id():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),   # current_database()
        MagicMock(scalar=lambda: "127.0.0.1"),       # inet_server_addr()
        MagicMock(scalar=lambda: "roms_test_user"),  # current_user
        MagicMock(scalar=lambda: 120),               # uptime
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # 0 tables
        MagicMock(scalar=lambda: "run-target-abc"),  # current_setting('roms.run_id')
        None,  # table creation
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db",
        run_id="run-target-abc",
    )

    guid = bootstrap_disposable_test_database(
        mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
    )
    assert guid.startswith("roms-test-")


def test_bootstrap_disposable_test_database_refuses_run_id_mismatch():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalar=lambda: "roms_test_user"),
        MagicMock(scalar=lambda: 120),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
        MagicMock(scalar=lambda: "wrong-run-id"),  # mismatch!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://roms_test_user:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="roms_test_user",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db",
        run_id="expected-run-id",
    )

    with pytest.raises(TargetVerificationRefusal, match="Container identity mismatch"):
        bootstrap_disposable_test_database(
            mock_conn, target, confirmation_token=BOOTSTRAP_CONFIRMATION_TOKEN
        )


def test_verify_disposable_test_target_with_matching_run_id():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),  # marker valid
        MagicMock(scalar=lambda: "run-target-abc"),        # server setting
        MagicMock(scalar=lambda: "run-target-abc"),        # marker table run_id
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db",
        run_id="run-target-abc",
    )

    # Should succeed without error
    verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_refuses_server_run_id_mismatch():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),
        MagicMock(scalar=lambda: "different-run-id"),  # server mismatch!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db",
        run_id="my-run-id",
    )

    with pytest.raises(TargetVerificationRefusal, match="Container identity mismatch"):
        verify_disposable_test_target(mock_conn, target)


def test_verify_disposable_test_target_refuses_marker_run_id_mismatch():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),
        MagicMock(scalar=lambda: "my-run-id"),     # server matches
        MagicMock(scalar=lambda: "old-run-id"),    # marker mismatch!
    ]

    target = ParsedPostgresTestTarget(
        raw_url="postgresql+psycopg://u:p@127.0.0.1:5433/roms_test_db",
        redacted_url="postgresql+psycopg://u:****@127.0.0.1:5433/roms_test_db",
        scheme="postgresql+psycopg",
        username="u",
        host="127.0.0.1",
        port=5433,
        database="roms_test_db",
        run_id="my-run-id",
    )

    with pytest.raises(TargetVerificationRefusal, match="Marker run ID mismatch"):
        verify_disposable_test_target(mock_conn, target)


