"""
Unit Tests for Isolated Test Database Migration Runner (OP-02)

Validates:
- Refusal on missing dedicated test DSN.
- Refusal on application DSN collision.
- Refusal when marker table is missing or invalid.
- Refusal on unexpected migration head or DAG anomaly.
- Refusal on unexpected existing revision state.
- Injection of pre-verified connection into Alembic.
- Strict zero-fallback to application settings.
- Universal credential sanitization on failure paths.

ZERO database connections are made during these tests (all drivers and engines are mocked).
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from scripts.migrate_postgres_test_db import run_isolated_test_migration
from tests.postgres_guard import (
    ConfigurationError,
    TargetVerificationRefusal,
    MigrationGraphError,
    EXPECTED_MIGRATION_HEAD,
)


def test_migrate_missing_dsn():
    with pytest.raises(ConfigurationError, match="not set or empty"):
        run_isolated_test_migration(raw_url=None, confirmation=True)

    with pytest.raises(ConfigurationError, match="not set or empty"):
        run_isolated_test_migration(raw_url="  ", confirmation=True)


def test_migrate_missing_confirmation():
    with pytest.raises(TargetVerificationRefusal, match="explicit confirmation"):
        run_isolated_test_migration(
            raw_url="postgresql+psycopg://roms_test_user:p@127.0.0.1:5433/roms_test_db",
            confirmation=False
        )


def test_migrate_app_dsn_collision(monkeypatch):
    app_url = "postgresql+psycopg://app_user:secret@127.0.0.1:5432/app_db"
    monkeypatch.setenv("DATABASE_URL", app_url)

    with pytest.raises(ConfigurationError, match="matches the ambient DATABASE_URL"):
        run_isolated_test_migration(raw_url=app_url, confirmation=True)


def test_migrate_no_fallback_to_application_settings(monkeypatch):
    # Unset test DSN, set application DATABASE_URL
    monkeypatch.delenv("ROMS_POSTGRES_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app_user:secret@127.0.0.1:5432/app_db")

    with pytest.raises(ConfigurationError, match="not set or empty"):
        run_isolated_test_migration(raw_url=os.environ.get("ROMS_POSTGRES_TEST_DATABASE_URL"), confirmation=True)


def test_migrate_missing_marker_refusal():
    valid_test_url = "postgresql+psycopg://roms_test_user:secret_pw@127.0.0.1:5433/roms_test_db"

    # Mock engine connection where marker table is missing
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),  # current_database()
        MagicMock(scalar=lambda: "127.0.0.1"),      # inet_server_addr()
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["users", "businesses"])),  # tables without marker!
    ]

    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("sqlalchemy.create_engine", return_value=mock_engine):
        with pytest.raises(TargetVerificationRefusal, match="lacks the mandatory test marker table"):
            run_isolated_test_migration(raw_url=valid_test_url, confirmation=True)


def test_migrate_unexpected_migration_head():
    valid_test_url = "postgresql+psycopg://roms_test_user:secret_pw@127.0.0.1:5433/roms_test_db"
    mock_engine = MagicMock()

    with patch("scripts.migrate_postgres_test_db.verify_migration_dag_head", side_effect=MigrationGraphError("Unexpected head")):
        with patch("scripts.migrate_postgres_test_db.sa.create_engine", return_value=mock_engine):
            with pytest.raises(MigrationGraphError, match="Unexpected head"):
                run_isolated_test_migration(raw_url=valid_test_url, confirmation=True)


def test_migrate_already_at_head():
    valid_test_url = "postgresql+psycopg://roms_test_user:secret_pw@127.0.0.1:5433/roms_test_db"

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["roms_disposable_test_marker", "alembic_version"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),  # marker valid
        MagicMock(scalar=lambda: 1),  # alembic_version table exists
        MagicMock(scalar=lambda: EXPECTED_MIGRATION_HEAD),  # current_rev is already head!
    ]

    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("scripts.migrate_postgres_test_db.sa.create_engine", return_value=mock_engine):
        outcome = run_isolated_test_migration(raw_url=valid_test_url, confirmation=True)
        assert outcome == f"already_at_head:{EXPECTED_MIGRATION_HEAD}"


def test_migrate_explicit_connection_injection_used():
    valid_test_url = "postgresql+psycopg://roms_test_user:secret_pw@127.0.0.1:5433/roms_test_db"

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = [
        MagicMock(scalar=lambda: "roms_test_db"),
        MagicMock(scalar=lambda: "127.0.0.1"),
        MagicMock(scalars=lambda: MagicMock(all=lambda: ["roms_disposable_test_marker"])),
        MagicMock(fetchone=lambda: (True, "ROMS-OP02")),
        MagicMock(scalar=lambda: 0),  # alembic_version table does not exist initially
        MagicMock(scalar=lambda: EXPECTED_MIGRATION_HEAD),  # post_rev check matches head
        MagicMock(scalar=lambda: 1),  # check_con count exists
        MagicMock(scalar=lambda: 1),  # partial_idx count exists
    ]

    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("scripts.migrate_postgres_test_db.sa.create_engine", return_value=mock_engine):
        with patch("alembic.command.upgrade") as mock_upgrade:
            outcome = run_isolated_test_migration(raw_url=valid_test_url, confirmation=True)
            assert outcome == f"upgraded_to:{EXPECTED_MIGRATION_HEAD}"

            # Verify upgrade was called with connection injected
            mock_upgrade.assert_called_once()
            called_cfg = mock_upgrade.call_args[0][0]
            assert called_cfg.attributes["connection"] is mock_conn


def test_migrate_credential_redaction_on_failure():
    sensitive_pw = "SuperSecretUnmaskedPassword987"
    valid_test_url = f"postgresql+psycopg://roms_test_user:{sensitive_pw}@127.0.0.1:5433/roms_test_db"

    mock_engine = MagicMock()
    # Simulate a raw driver connection error that contains the sensitive password
    mock_engine.connect.side_effect = Exception(
        f'password authentication failed for "roms_test_user", password="{sensitive_pw}"'
    )

    with patch("scripts.migrate_postgres_test_db.sa.create_engine", return_value=mock_engine):
        with pytest.raises(TargetVerificationRefusal) as exc_info:
            run_isolated_test_migration(raw_url=valid_test_url, confirmation=True)

        err_msg = str(exc_info.value)
        assert sensitive_pw not in err_msg
        assert "****" in err_msg


def test_migrate_run_id_mismatch_refusal():
    valid_test_url = "postgresql+psycopg://roms_test_user:pass@127.0.0.1:5433/roms_test_db"
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("scripts.migrate_postgres_test_db.sa.create_engine", return_value=mock_engine):
        with patch("scripts.migrate_postgres_test_db.verify_disposable_test_target", side_effect=TargetVerificationRefusal("Container identity mismatch: expected run-1")):
            with pytest.raises(TargetVerificationRefusal, match="Container identity mismatch"):
                run_isolated_test_migration(
                    raw_url=valid_test_url, confirmation=True, expected_run_id="run-1"
                )

