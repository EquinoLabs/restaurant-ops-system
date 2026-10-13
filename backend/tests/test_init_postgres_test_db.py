"""
Unit tests for ROMS Test Database Bootstrap CLI (OP-02)

Validates CLI argument parsing, confirmation requirement, run ID correlation,
and fail-closed behavior without establishing real database connections.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from scripts.init_postgres_test_db import main
from tests.postgres_guard import TargetVerificationRefusal, BOOTSTRAP_CONFIRMATION_TOKEN


def test_init_cli_refuses_without_confirm_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["init_postgres_test_db.py"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_init_cli_refuses_missing_database_url(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["init_postgres_test_db.py", "--confirm-bootstrap"])
    monkeypatch.delenv("ROMS_POSTGRES_TEST_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_init_cli_refuses_run_id_mismatch_with_env(monkeypatch):
    test_url = "postgresql+psycopg://roms_test_user:pass@127.0.0.1:5433/roms_test_db"
    monkeypatch.setenv("ROMS_POSTGRES_TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("ROMS_POSTGRES_TEST_RUN_ID", "env-run-id-123")
    monkeypatch.setattr(
        sys, "argv", ["init_postgres_test_db.py", "--confirm-bootstrap", "--run-id", "cli-run-id-999"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_init_cli_success_with_matching_run_id(monkeypatch):
    test_url = "postgresql+psycopg://roms_test_user:pass@127.0.0.1:5433/roms_test_db"
    monkeypatch.setenv("ROMS_POSTGRES_TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("ROMS_POSTGRES_TEST_RUN_ID", "shared-run-id")
    monkeypatch.setattr(
        sys, "argv", ["init_postgres_test_db.py", "--confirm-bootstrap", "--run-id", "shared-run-id"]
    )

    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("scripts.init_postgres_test_db.sa.create_engine", return_value=mock_engine):
        with patch("scripts.init_postgres_test_db.bootstrap_disposable_test_database", return_value="roms-test-guid-abc"):
            # Should exit cleanly (no unhandled exception)
            main()
            mock_engine.dispose.assert_called_once()


def test_init_cli_target_verification_refusal_fails_closed(monkeypatch):
    test_url = "postgresql+psycopg://roms_test_user:pass@127.0.0.1:5433/roms_test_db"
    monkeypatch.setenv("ROMS_POSTGRES_TEST_DATABASE_URL", test_url)
    monkeypatch.setattr(sys, "argv", ["init_postgres_test_db.py", "--confirm-bootstrap"])

    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("scripts.init_postgres_test_db.sa.create_engine", return_value=mock_engine):
        with patch("scripts.init_postgres_test_db.bootstrap_disposable_test_database", side_effect=TargetVerificationRefusal("Target contains existing tables")):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            mock_engine.dispose.assert_called_once()
