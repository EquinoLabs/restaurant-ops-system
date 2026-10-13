"""
ROMS Platform Governance — Initial User Provisioning Unit & Guard Tests (OP-04 Phase C1)

Verifies safeguards for provision_initial_user.py:
1. Missing required target environment.
2. Missing explicit confirmation.
3. Invalid or forbidden database target.
4. Pooled endpoint rejection.
5. Project, branch, endpoint, database, or schema-revision mismatch.
6. Missing or mismatched interactive password confirmation.
7. Existing email rejection without account modification.
8. Successful base-account creation in an isolated test database.
9. Correct initial role/status fields.
10. Audit logging failure causes a complete rollback.
11. No password or database secret appears in stdout, stderr, or logs.
12. C1 does not invoke or perform Owner promotion.
13. Active Owner count remains zero after successful provisioning.
"""

import pytest
import uuid
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.security import hash_password, verify_password
from app.core.errors import ValidationError
from scripts.provision_initial_user import (
    validate_provisioning_database_target,
    verify_provisioning_target_connection,
    prompt_for_initial_password,
    provision_initial_user_service,
    provision_initial_user,
    TargetVerificationRefusal,
    AUTHORIZED_PROVISIONING_EMAIL,
    NEON_EXPECTED_PROJECT_ID,
    NEON_EXPECTED_BRANCH_ID,
    NEON_FORBIDDEN_SOURCE_BRANCH_ID,
    NEON_EXPECTED_ENDPOINT_ID,
    NEON_EXPECTED_DATABASE,
    EXPECTED_MIGRATION_HEAD,
)


# ==============================================================================
# 1. Target Environment & Pre-Connection Validation Tests
# ==============================================================================

def test_validate_target_env_missing_fails_closed():
    """Requirement 1: Missing required target environment fails closed."""
    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_provisioning_database_target(None)

    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_provisioning_database_target("")


def test_validate_target_env_invalid_fails_closed():
    """Requirement 3: Invalid target environment fails closed."""
    with pytest.raises(ValidationError, match="Invalid target environment"):
        validate_provisioning_database_target("invalid_environment")


def test_validate_target_env_production_with_localhost_fails_closed():
    """Requirement 3: Production targeting localhost fails closed."""
    with pytest.raises(ValidationError, match="cannot target a localhost/loopback database"):
        validate_provisioning_database_target(
            target_env="production",
            database_uri="postgresql://user:pass@localhost:5432/neondb",
            explicit_database_url="postgresql://user:pass@localhost:5432/neondb",
        )


def test_validate_target_env_production_without_explicit_url_fails_closed():
    """Requirement 3: Production without explicit DATABASE_URL fails closed."""
    with pytest.raises(ValidationError, match="requires an explicitly configured DATABASE_URL"):
        validate_provisioning_database_target(
            target_env="production",
            database_uri="postgresql://user:pass@localhost:5432/neondb",
            explicit_database_url="",
        )


def test_validate_target_env_local_with_remote_cloud_host_fails_closed():
    """Requirement 3: Local environment targeting remote cloud database fails closed."""
    with pytest.raises(ValidationError, match="Target environment mismatch"):
        validate_provisioning_database_target(
            target_env="local",
            database_uri="postgresql://user:pass@ep-remote.neon.tech:5432/neondb",
            explicit_database_url="postgresql://user:pass@ep-remote.neon.tech:5432/neondb",
        )


def test_validate_target_pooled_endpoint_rejected():
    """Requirement 4: Pooled endpoints (-pooler) are rejected."""
    pooled_dsn = "postgresql://user:pass@ep-lucky-band-b3tbsmfz-pooler.us-east-2.aws.neon.tech:5432/neondb"
    with pytest.raises(ValidationError, match="pooled endpoint"):
        validate_provisioning_database_target(
            target_env="staging",
            database_uri=pooled_dsn,
            explicit_database_url=pooled_dsn,
        )


def test_validate_target_direct_endpoint_accepted_and_redacted():
    """Pre-connection gate accepts direct endpoint and redacts password."""
    direct_dsn = "postgresql://sec_user:secret_password@ep-lucky-band-b3tbsmfz.us-east-2.aws.neon.tech:5432/neondb"
    info = validate_provisioning_database_target(
        target_env="staging",
        database_uri=direct_dsn,
        explicit_database_url=direct_dsn,
    )
    assert info["target_env"] == "staging"
    assert info["host"] == "ep-lucky-band-b3tbsmfz.us-east-2.aws.neon.tech"
    assert info["port"] == 5432
    assert info["database"] == "neondb"
    assert "secret_password" not in info["masked_uri"]
    assert ":****@" in info["masked_uri"]


# ==============================================================================
# 2. In-Connection Target Identity Verification Tests
# ==============================================================================

def test_verify_target_database_mismatch_fails_closed():
    """Requirement 5: Target database mismatch fails closed."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = ["wrong_db"]

    with pytest.raises(TargetVerificationRefusal, match="Target database identity mismatch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_project_mismatch_fails_closed():
    """Requirement 5: Neon project ID mismatch fails closed."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        "wrong-project-id",
    ]

    with pytest.raises(TargetVerificationRefusal, match="Neon project identity mismatch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_forbidden_source_branch_fails_closed():
    """Requirement 5: Forbidden source branch connection triggers critical violation."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        NEON_EXPECTED_PROJECT_ID,
        NEON_FORBIDDEN_SOURCE_BRANCH_ID,
    ]

    with pytest.raises(TargetVerificationRefusal, match="CRITICAL SAFETY VIOLATION: Connected to forbidden source branch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_branch_mismatch_fails_closed():
    """Requirement 5: Neon branch ID mismatch fails closed."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        NEON_EXPECTED_PROJECT_ID,
        "wrong-branch-id",
    ]

    with pytest.raises(TargetVerificationRefusal, match="Neon branch identity mismatch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_endpoint_mismatch_fails_closed():
    """Requirement 5: Neon endpoint ID mismatch fails closed."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        NEON_EXPECTED_PROJECT_ID,
        NEON_EXPECTED_BRANCH_ID,
        "wrong-endpoint-id",
    ]

    with pytest.raises(TargetVerificationRefusal, match="Neon endpoint identity mismatch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_revision_mismatch_fails_closed():
    """Requirement 5: Alembic schema revision mismatch fails closed."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        NEON_EXPECTED_PROJECT_ID,
        NEON_EXPECTED_BRANCH_ID,
        NEON_EXPECTED_ENDPOINT_ID,
        "0011_wrong_revision",
    ]

    with pytest.raises(TargetVerificationRefusal, match="Alembic revision mismatch"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_missing_alembic_table_fails_closed():
    """Requirement 5: Missing alembic_version table fails closed."""
    conn = MagicMock()

    def _side_effect(statement):
        text_str = str(statement)
        mock_result = MagicMock()
        if "current_database()" in text_str:
            mock_result.scalar.return_value = NEON_EXPECTED_DATABASE
        elif "neon.project_id" in text_str:
            mock_result.scalar.return_value = NEON_EXPECTED_PROJECT_ID
        elif "neon.branch_id" in text_str:
            mock_result.scalar.return_value = NEON_EXPECTED_BRANCH_ID
        elif "neon.endpoint_id" in text_str:
            mock_result.scalar.return_value = NEON_EXPECTED_ENDPOINT_ID
        elif "alembic_version" in text_str:
            raise Exception("relation alembic_version does not exist")
        return mock_result

    conn.execute.side_effect = _side_effect

    with pytest.raises(TargetVerificationRefusal, match="Alembic version table missing"):
        verify_provisioning_target_connection(conn, target_env="staging")


def test_verify_target_all_valid_passes():
    """Requirement 5: Matching all target parameters passes verification."""
    conn = MagicMock()
    conn.execute.return_value.scalar.side_effect = [
        NEON_EXPECTED_DATABASE,
        NEON_EXPECTED_PROJECT_ID,
        NEON_EXPECTED_BRANCH_ID,
        NEON_EXPECTED_ENDPOINT_ID,
        EXPECTED_MIGRATION_HEAD,
    ]
    # Must not raise
    verify_provisioning_target_connection(conn, target_env="staging")


# ==============================================================================
# 3. Credential Handling & Interactive Password Tests
# ==============================================================================

def test_prompt_password_mismatch_fails_closed():
    """Requirement 6: Mismatched password confirmation fails closed."""
    mock_getter = MagicMock(side_effect=["Password123!", "Mismatch456!"])
    with pytest.raises(ValidationError, match="Password confirmation does not match"):
        prompt_for_initial_password(password_getter=mock_getter)


def test_prompt_password_empty_fails_closed():
    """Requirement 6: Empty password input fails closed."""
    mock_getter = MagicMock(side_effect=["", ""])
    with pytest.raises(ValidationError, match="Password cannot be empty"):
        prompt_for_initial_password(password_getter=mock_getter)


def test_prompt_password_too_short_fails_closed():
    """Requirement 6: Short password fails closed."""
    mock_getter = MagicMock(side_effect=["short", "short"])
    with pytest.raises(ValidationError, match="at least 8 characters"):
        prompt_for_initial_password(password_getter=mock_getter)


def test_prompt_password_interactive_failure_fails_closed():
    """Requirement 6: Non-interactive EOFError fails closed."""
    mock_getter = MagicMock(side_effect=EOFError("EOF encountered"))
    with pytest.raises(ValidationError, match="Interactive password input failed"):
        prompt_for_initial_password(password_getter=mock_getter)


def test_prompt_password_valid_returns_password():
    """Requirement 6: Matching valid passwords successfully returned."""
    mock_getter = MagicMock(side_effect=["ValidPass123!", "ValidPass123!"])
    result = prompt_for_initial_password(password_getter=mock_getter)
    assert result == "ValidPass123!"


# ==============================================================================
# 4. Confirmation Guard & Invariant Tests
# ==============================================================================

def test_provision_service_confirm_false_writes_nothing(db_session: Session):
    """Requirement 2: confirm=False applies zero mutations and creates no account."""
    success = provision_initial_user_service(
        db=db_session,
        confirm=False,
        password_hash=hash_password("ValidPassword123!"),
    )
    assert success is False
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is None


def test_provision_unauthorized_email_fails_closed(db_session: Session):
    """Requirement C: Non-authorized email is rejected to prevent arbitrary account creation."""
    with pytest.raises(ValidationError, match="Unauthorized account provisioning"):
        provision_initial_user_service(
            db=db_session,
            email="attacker@roms.com",
            confirm=True,
            password_hash=hash_password("ValidPassword123!"),
        )


def test_provision_existing_email_rejected_without_modification(db_session: Session):
    """Requirement 7: Existing user is rejected without modifying existing record."""
    existing_pw_hash = hash_password("OriginalPassword123!")
    existing_user = User(
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=existing_pw_hash,
        display_name="Existing User",
        status="active",
        is_platform_admin=False,
        platform_role=None,
    )
    db_session.add(existing_user)
    db_session.commit()

    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        confirm=True,
        password_hash=hash_password("NewAttemptPassword456!"),
    )
    assert success is False

    db_session.refresh(existing_user)
    assert existing_user.display_name == "Existing User"
    assert existing_user.password_hash == existing_pw_hash
    assert verify_password("OriginalPassword123!", existing_user.password_hash) is True

    # Cleanup
    db_session.delete(existing_user)
    db_session.commit()


def test_provision_preexisting_owner_fails_closed(db_session: Session):
    """Initial provisioning fails closed if an active Platform Owner already exists."""
    owner_user = User(
        email="preexisting.owner@roms.com",
        password_hash=hash_password("OwnerPassword123!"),
        display_name="Preexisting Owner",
        status="active",
        is_platform_admin=True,
        platform_role="owner",
    )
    db_session.add(owner_user)
    db_session.commit()

    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        confirm=True,
        password_hash=hash_password("SomePassword123!"),
    )
    assert success is False

    # Cleanup
    db_session.delete(owner_user)
    db_session.commit()


# ==============================================================================
# 5. Successful Base-Account Creation & Field Verification Tests
# ==============================================================================

def test_provision_successful_base_account_creation(db_session: Session):
    """
    Requirements 8, 9, 12, 13:
    - Base account created in isolated DB.
    - Correct fields: status='active', platform_role=None, is_platform_admin=False.
    - Owner promotion NOT invoked.
    - Active Owner count remains strictly 0.
    """
    # Verify baseline active owner count is zero
    assert db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count() == 0

    plain_pass = "ComplexSecretPassword789!"
    hashed_pass = hash_password(plain_pass)

    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=hashed_pass,
        display_name="Platform Owner",
        confirm=True,
        operator="ops.lead@example.com",
        target_env="test",
    )
    assert success is True
    db_session.commit()

    # Query newly created account
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is not None
    assert user.email == "owner@roms.com"
    assert user.display_name == "Platform Owner"
    assert user.status == "active"

    # Invariant checks: Unprivileged base user
    assert user.platform_role is None
    assert user.is_platform_admin is False

    # Verify password authentication matches
    assert verify_password(plain_pass, user.password_hash) is True
    assert verify_password("WrongPassword!", user.password_hash) is False

    # Invariant check: Active Owner count remains strictly 0
    active_owners = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owners == 0

    # Verify audit event
    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "platform.user.provision", AuditLog.entity_id == user.id)
        .first()
    )
    assert audit_entry is not None
    meta = audit_entry.metadata_json
    assert meta["action_type"] == "platform.user.provision"
    assert meta["target_email"] == "owner@roms.com"
    assert meta["assigned_role"] is None
    assert meta["is_platform_admin"] is False
    assert meta["status"] == "active"
    assert meta["operator"] == "ops.lead@example.com"
    assert meta["outcome"] == "success"

    # Cleanup
    db_session.delete(audit_entry)
    db_session.delete(user)
    db_session.commit()


# ==============================================================================
# 6. Audit Logging Failure Rollback Tests
# ==============================================================================

def test_provision_audit_failure_causes_complete_rollback(db_session: Session):
    """Requirement 10: Audit logging failure causes complete rollback."""
    with patch("scripts.provision_initial_user.log_audit", side_effect=RuntimeError("Audit disk write failed")):
        with pytest.raises(RuntimeError, match="Audit disk write failed"):
            provision_initial_user_service(
                db=db_session,
                confirm=True,
                password_hash=hash_password("ValidPassword123!"),
            )
        db_session.rollback()

    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is None


# ==============================================================================
# 7. Redaction & Credential Secrecy Tests
# ==============================================================================

def test_no_password_or_secret_appears_in_stdout_or_stderr(capsys, db_session: Session):
    """Requirement 11: No plaintext password, password hash, or DB secret appears in stdout/stderr."""
    plain_pass = "UltraSecretPassword999!"
    hashed_pass = hash_password(plain_pass)

    success = provision_initial_user_service(
        db=db_session,
        confirm=True,
        password_hash=hashed_pass,
        display_name="Platform Owner",
    )
    assert success is True
    db_session.commit()

    captured = capsys.readouterr()

    # Plaintext password must never appear
    assert plain_pass not in captured.out
    assert plain_pass not in captured.err

    # Bcrypt password hash prefix must never appear
    assert "$2b$" not in captured.out
    assert "$2b$" not in captured.err

    # Cleanup
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    if user:
        audit_entry = db_session.query(AuditLog).filter(AuditLog.entity_id == user.id).first()
        if audit_entry:
            # Audit metadata must never contain secrets
            assert plain_pass not in str(audit_entry.metadata_json)
            assert "$2b$" not in str(audit_entry.metadata_json)
            db_session.delete(audit_entry)
        db_session.delete(user)
        db_session.commit()


# ==============================================================================
# 8. Script-Owned Mode & CLI Entrypoint Tests
# ==============================================================================

MOCK_DIRECT_TARGET = {
    "target_env": "test",
    "host": "ep-lucky-band-b3tbsmfz.c-4.ap-southeast-1.aws.neon.tech",
    "port": 5432,
    "database": "neondb",
    "scheme": "postgresql+psycopg",
    "masked_uri": "postgresql+psycopg://user:****@ep-lucky-band-b3tbsmfz.c-4.ap-southeast-1.aws.neon.tech/neondb",
    "is_explicit": True,
}


def test_provision_script_owned_mode_success(db_session: Session):
    """Verifies script-owned mode creates and commits user when SessionLocal is used."""
    with patch("scripts.provision_initial_user.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.provision_initial_user.SessionLocal", return_value=db_session), \
         patch.object(db_session, "close"):
        success = provision_initial_user(
            email=AUTHORIZED_PROVISIONING_EMAIL,
            password_hash=hash_password("Pass123456!"),
            confirm=True,
            target_env="test",
        )
        assert success is True

    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is not None

    # Cleanup
    audit_entry = db_session.query(AuditLog).filter(AuditLog.entity_id == user.id).first()
    if audit_entry:
        db_session.delete(audit_entry)
    db_session.delete(user)
    db_session.commit()


def test_cli_dry_run_exits_zero_writes_nothing(capsys, db_session: Session):
    """CLI preflight/dry-run inspection exits 0 and writes zero database records."""
    from scripts.provision_initial_user import main
    test_args = ["provision_initial_user.py", "--target-env", "test"]
    with patch("sys.argv", test_args), \
         patch("scripts.provision_initial_user.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.provision_initial_user.SessionLocal", return_value=db_session), \
         patch.object(db_session, "close"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ROMS INITIAL USER PROVISIONING PREFLIGHT / DRY-RUN" in captured.out
    assert "DRY-RUN ONLY: Zero database changes were written" in captured.out

    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is None


def test_cli_unauthorized_email_fails_with_exit_code_1(capsys):
    """CLI rejects unauthorized email argument and exits 1 before session initialization."""
    from scripts.provision_initial_user import main
    test_args = ["provision_initial_user.py", "--target-env", "test", "--email", "unauth@roms.com"]
    with patch("sys.argv", test_args), \
         patch("scripts.provision_initial_user.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Unauthorized account provisioning" in captured.err


def test_cli_confirmed_execution_success(capsys, db_session: Session):
    """CLI confirmed execution creates user and emits audit log without exposing passwords."""
    from scripts.provision_initial_user import main
    test_args = ["provision_initial_user.py", "--target-env", "test", "--confirm", "--operator", "lead.ops@example.com"]
    with patch("sys.argv", test_args), \
         patch("scripts.provision_initial_user.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.provision_initial_user.SessionLocal", return_value=db_session), \
         patch.object(db_session, "close"), \
         patch("scripts.provision_initial_user.prompt_for_initial_password", return_value="StrongPassword123!"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ROMS INITIAL USER PROVISIONED & COMMITTED" in captured.out
    assert "StrongPassword123!" not in captured.out
    assert "$2b$" not in captured.out

    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is not None
    assert user.status == "active"
    assert user.platform_role is None
    assert user.is_platform_admin is False

    # Cleanup
    audit_entry = db_session.query(AuditLog).filter(AuditLog.entity_id == user.id).first()
    if audit_entry:
        db_session.delete(audit_entry)
    db_session.delete(user)
    db_session.commit()


# ==============================================================================
# 9. Automated Test-Only Credential Workflow & Dynamic Lifecycle Tests
# ==============================================================================

import secrets


@pytest.fixture
def dynamic_test_credentials():
    """
    Test-only credential fixture:
    - Generates a cryptographically strong, non-deterministic random password in memory.
    - Hashes it using the existing Bcrypt implementation.
    - Yields (plain_password, password_hash) to the test.
    - Plaintext is cleared from the fixture scope upon teardown.
    """
    raw_password = f"TestPass_{secrets.token_urlsafe(24)}!A1"
    pw_hash = hash_password(raw_password)
    yield raw_password, pw_hash
    # Secure teardown
    del raw_password
    del pw_hash


def test_automated_bootstrap_dynamic_credential_workflow(db_session: Session, dynamic_test_credentials, capsys):
    """
    Verifies that the bootstrap domain service can be tested directly with
    dynamically generated in-memory credentials without requiring interactive getpass.
    Asserts:
    1. Base account is created with correct unprivileged fields.
    2. Authentication succeeds for the dynamic password and fails for wrong passwords.
    3. Neither plaintext password nor hash appears in captured stdout/stderr.
    4. Audit metadata contains zero credentials.
    5. Cleanup removes exact records without leaving residue.
    """
    raw_pass, pw_hash = dynamic_test_credentials

    # 1. Execute bootstrap domain service directly with pre-computed hash
    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=pw_hash,
        display_name="Platform Owner",
        confirm=True,
        operator="test_automation_runner@roms.com",
        target_env="test",
    )
    assert success is True
    db_session.commit()

    # 2. Query and verify newly created user
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is not None
    assert user.status == "active"
    assert user.platform_role is None
    assert user.is_platform_admin is False

    # 3. Verify password authentication
    assert verify_password(raw_pass, user.password_hash) is True
    assert verify_password("IncorrectPasswordAttempt!", user.password_hash) is False

    # 4. Assert zero credential exposure in output streams
    captured = capsys.readouterr()
    assert raw_pass not in captured.out
    assert raw_pass not in captured.err
    assert "$2b$" not in captured.out
    assert "$2b$" not in captured.err

    # 5. Assert audit log exists with clean metadata
    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "platform.user.provision", AuditLog.entity_id == user.id)
        .first()
    )
    assert audit_entry is not None
    meta = audit_entry.metadata_json or {}
    assert meta.get("target_email") == AUTHORIZED_PROVISIONING_EMAIL
    assert meta.get("assigned_role") is None
    assert meta.get("is_platform_admin") is False
    assert raw_pass not in str(meta)
    assert "$2b$" not in str(meta)

    # 6. Exact ID cleanup
    db_session.delete(audit_entry)
    db_session.delete(user)
    db_session.commit()

    assert db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first() is None


def test_prompt_for_initial_password_with_test_callable_getter(dynamic_test_credentials):
    """
    Verifies that prompt_for_initial_password supports a custom password_getter callable,
    allowing non-interactive test suites to exercise prompt confirmation logic safely.
    """
    raw_pass, _ = dynamic_test_credentials

    # Test getter providing matching passwords
    mock_getter = MagicMock(side_effect=[raw_pass, raw_pass])
    result = prompt_for_initial_password(password_getter=mock_getter)
    assert result == raw_pass
    assert mock_getter.call_count == 2

    # Test getter providing mismatched passwords
    mismatch_getter = MagicMock(side_effect=[raw_pass, "DifferentPassword999!"])
    with pytest.raises(ValidationError, match="Password confirmation does not match"):
        prompt_for_initial_password(password_getter=mismatch_getter)


def test_automated_bootstrap_script_owned_mode_with_dynamic_credentials(db_session: Session, dynamic_test_credentials):
    """
    Verifies top-level provision_initial_user helper in script-owned mode using
    dynamically generated credentials and exact-ID cleanup.
    """
    _, pw_hash = dynamic_test_credentials

    with patch("scripts.provision_initial_user.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.provision_initial_user.SessionLocal", return_value=db_session), \
         patch.object(db_session, "close"):
        success = provision_initial_user(
            email=AUTHORIZED_PROVISIONING_EMAIL,
            password_hash=pw_hash,
            display_name="Platform Owner",
            confirm=True,
            target_env="test",
            operator="automated_ci@roms.com",
        )
        assert success is True

    # Confirm user created and active owner count remains 0
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is not None
    assert user.platform_role is None
    assert user.is_platform_admin is False

    active_owners = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owners == 0

    # Exact cleanup
    audit_entry = db_session.query(AuditLog).filter(AuditLog.entity_id == user.id).first()
    if audit_entry:
        db_session.delete(audit_entry)
    db_session.delete(user)
    db_session.commit()


# ==============================================================================
# 10. Smoke Test Runner & Exact-ID Teardown Safeguard Tests
# ==============================================================================

from scripts.run_safety_branch_bootstrap_test import (
    check_preexisting_target_account,
    format_preexisting_account_report,
    teardown_test_records,
    run_c1_bootstrap_test,
    EXPECTED_PREEXISTING_USERS,
)


def seed_preexisting_canonical_users(session: Session) -> List[User]:
    """Helper to seed the 4 canonical pre-existing users."""
    users = []
    for email, meta in EXPECTED_PREEXISTING_USERS.items():
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            users.append(existing)
            continue
        u = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password("PreExistingPass123!"),
            display_name=email.split("@")[0],
            status=meta["status"],
            platform_role=meta["platform_role"],
            is_platform_admin=meta["is_platform_admin"],
        )
        users.append(u)
        session.add(u)
    session.commit()
    return users


def test_smoke_test_exact_id_cleanup_isolates_preexisting_users(db_session: Session, dynamic_test_credentials):
    """
    Verifies that teardown_test_records deletes ONLY the explicitly tracked
    user and audit event matching created_user_id and created_audit_id.
    Asserts:
    1. Pre-existing users are untouched.
    2. Unrelated audit logs are untouched.
    3. Active platform owner count remains 0.
    """
    raw_pass, pw_hash = dynamic_test_credentials

    # 1. Seed 4 pre-existing users
    pre_users = seed_preexisting_canonical_users(db_session)
    admin_user = next(u for u in pre_users if u.email == "admin@himachalhospitality.com")

    # 2. Seed an unrelated pre-existing audit log
    unrelated_audit = AuditLog(
        id=uuid.uuid4(),
        business_id=None,
        outlet_id=None,
        actor_user_id=admin_user.id,
        action="platform.outlet.update",
        entity_type="outlet",
        entity_id=uuid.uuid4(),
        metadata_json={"operation": "unrelated_preexisting_action"},
    )
    db_session.add(unrelated_audit)
    db_session.commit()

    # 3. Provision the target user
    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=pw_hash,
        display_name="Platform Owner",
        confirm=True,
        target_env="test",
        operator="smoke_test@roms.com",
    )
    assert success is True
    db_session.commit()

    created_user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).one()
    created_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "platform.user.provision", AuditLog.entity_id == created_user.id)
        .one()
    )

    created_user_id = created_user.id
    created_audit_id = created_audit.id

    # 4. Execute exact-ID teardown
    result = teardown_test_records(
        session=db_session,
        user_id=created_user_id,
        audit_id=created_audit_id,
    )
    assert result["status"] == "success"
    assert result["deleted_user_id"] == str(created_user_id)
    assert result["deleted_audit_id"] == str(created_audit_id)

    # 5. Assert target records are deleted
    assert db_session.query(User).filter(User.id == created_user_id).first() is None
    assert db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first() is None
    assert db_session.query(AuditLog).filter(AuditLog.id == created_audit_id).first() is None

    # 6. Assert unrelated audit log is intact
    retained_audit = db_session.query(AuditLog).filter(AuditLog.id == unrelated_audit.id).first()
    assert retained_audit is not None
    assert retained_audit.action == "platform.outlet.update"

    # 7. Assert 4 canonical pre-existing users remain intact
    post_users = {u.email: u for u in db_session.query(User).all()}
    for email, expected in EXPECTED_PREEXISTING_USERS.items():
        assert email in post_users
        actual = post_users[email]
        assert actual.status == expected["status"]
        assert actual.platform_role == expected["platform_role"]
        assert actual.is_platform_admin == expected["is_platform_admin"]

    # 8. Assert active owner count remains 0
    active_owners = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owners == 0

    # Cleanup unrelated audit log
    db_session.delete(unrelated_audit)
    db_session.commit()


def test_smoke_test_teardown_fails_closed_on_none_or_mismatched_ids(db_session: Session):
    """
    Verifies that teardown_test_records fails closed:
    - Rejects None for user_id or audit_id.
    - Rejects mismatched IDs without deleting any records.
    """
    # Reject None user_id
    with pytest.raises(ValueError, match="user_id and audit_id must both be non-None"):
        teardown_test_records(db_session, user_id=None, audit_id=uuid.uuid4())

    # Reject None audit_id
    with pytest.raises(ValueError, match="user_id and audit_id must both be non-None"):
        teardown_test_records(db_session, user_id=uuid.uuid4(), audit_id=None)

    # Reject non-existent IDs
    fake_user_id = uuid.uuid4()
    fake_audit_id = uuid.uuid4()
    with pytest.raises(RuntimeError, match="Teardown failure"):
        teardown_test_records(db_session, user_id=fake_user_id, audit_id=fake_audit_id)


def test_smoke_test_preflight_blocks_and_reports_existing_target_account(db_session: Session):
    """
    Verifies that check_preexisting_target_account correctly detects existing account,
    format_preexisting_account_report generates non-destructive diagnostic report,
    and execution halts without modifying or deleting the account.
    """
    # 1. When user does not exist
    assert check_preexisting_target_account(db_session) is None

    # 2. Seed existing user
    existing_user = User(
        id=uuid.uuid4(),
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=hash_password("ExistingSecretPass123!"),
        display_name="Pre-existing Account",
        status="active",
        platform_role=None,
        is_platform_admin=False,
    )
    db_session.add(existing_user)
    db_session.commit()

    # 3. Detect existing user
    info = check_preexisting_target_account(db_session)
    assert info is not None
    assert info["id"] == str(existing_user.id)
    assert info["email"] == AUTHORIZED_PROVISIONING_EMAIL
    assert info["status"] == "active"
    assert info["platform_role"] is None
    assert info["is_platform_admin"] is False

    # 4. Format report
    report = format_preexisting_account_report(info)
    assert "PREFLIGHT REFUSAL" in report
    assert str(existing_user.id) in report
    assert "The smoke test will NOT delete, overwrite, or mutate this account" in report

    # 5. Verify existing user was NOT modified
    db_session.refresh(existing_user)
    assert existing_user.display_name == "Pre-existing Account"

    # Cleanup
    db_session.delete(existing_user)
    db_session.commit()


def test_smoke_test_dynamic_password_authentication_positive_and_negative(db_session: Session):
    """
    Verifies that dynamically generated secrets.token_urlsafe(32) password:
    1. Authenticates successfully against stored hash.
    2. Rejects incorrect password attempts.
    """
    dynamic_pass = secrets.token_urlsafe(32)
    pw_hash = hash_password(dynamic_pass)

    success = provision_initial_user_service(
        db=db_session,
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=pw_hash,
        display_name="Platform Owner",
        confirm=True,
        target_env="test",
        operator="auth_test@roms.com",
    )
    assert success is True
    db_session.commit()

    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).one()

    # Positive authentication
    assert verify_password(dynamic_pass, user.password_hash) is True

    # Negative authentication attempts
    assert verify_password("WrongPass_" + secrets.token_urlsafe(16), user.password_hash) is False
    assert verify_password("DifferentPassword999!", user.password_hash) is False
    assert verify_password("", user.password_hash) is False

    # Cleanup
    audit = db_session.query(AuditLog).filter(AuditLog.entity_id == user.id).first()
    if audit:
        db_session.delete(audit)
    db_session.delete(user)
    db_session.commit()


def test_smoke_test_atomicity_and_rollback_on_audit_failure(db_session: Session):
    """
    Verifies that if audit creation fails during provisioning:
    1. Transaction is rolled back.
    2. User account is not created.
    3. Active owner count remains 0.
    4. Database state remains clean.
    """
    pw_hash = hash_password(secrets.token_urlsafe(32))

    with patch("scripts.provision_initial_user.log_audit", side_effect=RuntimeError("Audit write failure")):
        with pytest.raises(RuntimeError, match="Audit write failure"):
            provision_initial_user_service(
                db=db_session,
                email=AUTHORIZED_PROVISIONING_EMAIL,
                password_hash=pw_hash,
                confirm=True,
                target_env="test",
            )
        db_session.rollback()

    # User must not exist
    user = db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first()
    assert user is None

    # Active owners count must remain 0
    active_owners = db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count()
    assert active_owners == 0


def test_smoke_test_end_to_end_runner_with_teardown(db_session: Session):
    """
    Executes the full run_c1_bootstrap_test runner with teardown=True
    using a mock session factory and verified SQLite environment.
    """
    # Setup alembic_version table in SQLite
    db_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db_session.execute(text("DELETE FROM alembic_version"))
    db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0012_platform_role_constraints')"))
    db_session.commit()

    # Seed 4 canonical pre-existing users
    seed_preexisting_canonical_users(db_session)

    with patch("scripts.run_safety_branch_bootstrap_test.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.run_safety_branch_bootstrap_test.verify_provisioning_target_connection", return_value=None):
        result = run_c1_bootstrap_test(
            target_env="test",
            teardown=True,
            session_factory=lambda: db_session,
        )

    assert result["status"] == "success"
    assert result["auth_verified"] is True
    assert result["teardown_performed"] is True
    assert result["teardown_result"]["status"] == "success"

    # Confirm target account was torn down
    assert db_session.query(User).filter(User.email == AUTHORIZED_PROVISIONING_EMAIL).first() is None

    # Confirm 4 pre-existing users remain intact
    post_users = {u.email: u for u in db_session.query(User).all()}
    for email in EXPECTED_PREEXISTING_USERS:
        assert email in post_users

    # Confirm active owner count is 0
    assert db_session.query(User).filter(User.platform_role == "owner", User.status == "active").count() == 0


def test_smoke_test_end_to_end_runner_blocks_on_existing_account(db_session: Session):
    """
    Executes run_c1_bootstrap_test when target account already exists.
    Verifies that runner raises RuntimeError, leaves account intact,
    and does not execute write or teardown.
    """
    # Setup alembic_version table
    db_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db_session.execute(text("DELETE FROM alembic_version"))
    db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0012_platform_role_constraints')"))
    db_session.commit()

    # Seed 4 pre-existing users
    seed_preexisting_canonical_users(db_session)

    # Seed target account
    existing_user = User(
        id=uuid.uuid4(),
        email=AUTHORIZED_PROVISIONING_EMAIL,
        password_hash=hash_password("PreExistingPass123!"),
        display_name="Initial Platform Owner",
        status="active",
        platform_role=None,
        is_platform_admin=False,
    )
    db_session.add(existing_user)
    db_session.commit()
    existing_id = existing_user.id

    with patch("scripts.run_safety_branch_bootstrap_test.validate_provisioning_database_target", return_value=MOCK_DIRECT_TARGET), \
         patch("scripts.run_safety_branch_bootstrap_test.verify_provisioning_target_connection", return_value=None):
        with pytest.raises(RuntimeError, match="already exists"):
            run_c1_bootstrap_test(
                target_env="test",
                teardown=True,
                session_factory=lambda: db_session,
            )

    # Verify existing account is completely intact
    user_after = db_session.query(User).filter(User.id == existing_id).first()
    assert user_after is not None
    assert user_after.email == AUTHORIZED_PROVISIONING_EMAIL
    assert user_after.display_name == "Initial Platform Owner"

    # Cleanup
    db_session.delete(user_after)
    db_session.commit()



