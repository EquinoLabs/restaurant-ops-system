import pytest
import uuid
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from app.modules.staff.models import User
from app.modules.audit.models import AuditLog
from app.core.errors import ValidationError
from scripts.create_platform_admin import (
    validate_bootstrap_database_target,
    promote_user_to_platform_admin_service,
    promote_user_to_platform_admin,
    _get_execution_context,
)


# ==============================================================================
# 1. Target Environment & DSN Safety Validation Tests
# ==============================================================================

def test_validate_bootstrap_target_env_missing_fails_closed():
    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_bootstrap_database_target(None)

    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_bootstrap_database_target("")


def test_validate_bootstrap_target_env_invalid_fails_closed():
    with pytest.raises(ValidationError, match="Invalid target environment 'production-invalid'"):
        validate_bootstrap_database_target("production-invalid")


def test_validate_bootstrap_target_env_production_with_implicit_fallback_fails_closed():
    # If explicit_database_url is empty/None in production, fail closed
    with pytest.raises(ValidationError, match="requires an explicitly configured DATABASE_URL"):
        validate_bootstrap_database_target(
            target_env="production",
            database_uri="postgresql://user:pass@localhost:5432/roms_db",
            explicit_database_url="",
        )


def test_validate_bootstrap_target_env_production_with_localhost_fails_closed():
    with pytest.raises(ValidationError, match="cannot target a localhost/loopback database"):
        validate_bootstrap_database_target(
            target_env="production",
            database_uri="postgresql://user:pass@localhost:5432/roms_db",
            explicit_database_url="postgresql://user:pass@localhost:5432/roms_db",
        )

    with pytest.raises(ValidationError, match="cannot target a localhost/loopback database"):
        validate_bootstrap_database_target(
            target_env="production",
            database_uri="postgresql://user:pass@127.0.0.1:5432/roms_db",
            explicit_database_url="postgresql://user:pass@127.0.0.1:5432/roms_db",
        )


def test_validate_bootstrap_target_env_local_with_remote_host_fails_closed():
    with pytest.raises(ValidationError, match="Target environment mismatch"):
        validate_bootstrap_database_target(
            target_env="local",
            database_uri="postgresql://user:pass@ep-remote.neon.tech:5432/neondb",
            explicit_database_url="postgresql://user:pass@ep-remote.neon.tech:5432/neondb",
        )


def test_validate_bootstrap_target_env_masks_credentials_securely():
    result = validate_bootstrap_database_target(
        target_env="production",
        database_uri="postgresql://secret_user:super_secret_password@remote-db.aws.neon.tech:5432/prod_db",
        explicit_database_url="postgresql://secret_user:super_secret_password@remote-db.aws.neon.tech:5432/prod_db",
    )
    assert result["target_env"] == "production"
    assert result["host"] == "remote-db.aws.neon.tech"
    assert result["port"] == 5432
    assert result["database"] == "prod_db"
    assert "super_secret_password" not in result["masked_uri"]
    assert ":****@" in result["masked_uri"]


# ==============================================================================
# 2. Confirmation Guard & Dry-Run Tests
# ==============================================================================

def test_bootstrap_service_confirm_false_writes_nothing(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    success = promote_user_to_platform_admin_service(
        db=db_session,
        email="staff@test.com",
        role="owner",
        confirm=False,
    )
    assert success is False

    db_session.refresh(user)
    assert user.platform_role is None
    assert user.is_platform_admin is False


def test_bootstrap_service_confirm_true_applies_changes(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    success = promote_user_to_platform_admin_service(
        db=db_session,
        email="staff@test.com",
        role="owner",
        confirm=True,
    )
    assert success is True

    db_session.refresh(user)
    assert user.platform_role == "owner"
    assert user.is_platform_admin is True

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


# ==============================================================================
# 3. Fail-Closed Target Validation Tests
# ==============================================================================

def test_bootstrap_empty_email_fails_closed(db_session: Session):
    assert promote_user_to_platform_admin_service(db_session, email="", role="owner") is False
    assert promote_user_to_platform_admin_service(db_session, email="   ", role="owner") is False


def test_bootstrap_nonexistent_user_fails_closed(db_session: Session):
    assert promote_user_to_platform_admin_service(
        db_session, email="ghost@nonexistent.com", role="owner"
    ) is False


def test_bootstrap_inactive_status_fails_closed(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "pending"
    db_session.commit()

    try:
        success = promote_user_to_platform_admin_service(
            db_session, email="staff@test.com", role="owner"
        )
        assert success is False
    finally:
        user.status = "active"
        db_session.commit()


def test_bootstrap_suspended_user_fails_closed(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.status = "suspended"
    db_session.commit()

    try:
        success = promote_user_to_platform_admin_service(
            db_session, email="staff@test.com", role="owner"
        )
        assert success is False
    finally:
        user.status = "active"
        db_session.commit()


def test_bootstrap_ambiguous_user_fails_closed(db_session: Session):
    # Mock query to return multiple matching users
    mock_u1 = MagicMock(spec=User, email="dup@test.com", status="active")
    mock_u2 = MagicMock(spec=User, email="dup@test.com", status="active")

    mock_db = MagicMock()
    mock_db.bind = None
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_u1, mock_u2]

    success = promote_user_to_platform_admin_service(mock_db, email="dup@test.com", role="owner")
    assert success is False
    mock_db.flush.assert_not_called()


# ==============================================================================
# 4. Owner Invariant Enforcement Tests
# ==============================================================================

def test_bootstrap_owner_success_when_zero_owners(db_session: Session):
    # Ensure zero active owners
    for u in db_session.query(User).filter(User.platform_role == "owner").all():
        u.platform_role = None
        u.is_platform_admin = False
    db_session.commit()

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    success = promote_user_to_platform_admin_service(
        db=db_session,
        email="staff@test.com",
        role="owner",
        confirm=True,
    )
    assert success is True

    db_session.refresh(user)
    assert user.platform_role == "owner"
    assert user.is_platform_admin is True

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


def test_bootstrap_second_owner_fails_closed_when_owner_exists(db_session: Session):
    # Set staff as active owner
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff.platform_role = "owner"
    staff.is_platform_admin = True
    staff.status = "active"
    db_session.commit()

    # Attempt to bootstrap candidate as second owner
    cand = db_session.query(User).filter(User.email == "unauth@test.com").first()
    cand.platform_role = None
    cand.is_platform_admin = False
    db_session.commit()

    try:
        success = promote_user_to_platform_admin_service(
            db=db_session,
            email="unauth@test.com",
            role="owner",
            confirm=True,
        )
        assert success is False

        db_session.refresh(cand)
        assert cand.platform_role is None
        assert cand.is_platform_admin is False
    finally:
        staff.platform_role = None
        staff.is_platform_admin = False
        db_session.commit()


def test_bootstrap_owner_idempotent_when_already_owner(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = "owner"
    user.is_platform_admin = True
    user.status = "active"
    db_session.commit()

    try:
        success = promote_user_to_platform_admin_service(
            db=db_session,
            email="staff@test.com",
            role="owner",
            confirm=True,
        )
        assert success is True

        db_session.refresh(user)
        assert user.platform_role == "owner"
        assert user.is_platform_admin is True
    finally:
        user.platform_role = None
        user.is_platform_admin = False
        db_session.commit()


# ==============================================================================
# 5. Structured Audit Logging Tests
# ==============================================================================

def test_bootstrap_owner_emits_structured_audit_event(db_session: Session):
    # Clear existing owners
    for u in db_session.query(User).filter(User.platform_role == "owner").all():
        u.platform_role = None
        u.is_platform_admin = False
    db_session.commit()

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    success = promote_user_to_platform_admin_service(
        db=db_session,
        email="staff@test.com",
        role="owner",
        confirm=True,
        operator="lead.security@example.com",
        target_env="test",
    )
    assert success is True

    # Verify audit log entry
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "platform.owner.bootstrap", AuditLog.entity_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.metadata_json["action_type"] == "platform.owner.bootstrap"
    assert audit.metadata_json["assigned_role"] == "owner"
    assert audit.metadata_json["target_email"] == "staff@test.com"
    assert audit.metadata_json["operator"] == "lead.security@example.com"
    assert audit.metadata_json["outcome"] == "success"
    assert "execution_host" in audit.metadata_json

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


def test_bootstrap_admin_emits_structured_audit_event(db_session: Session):
    user = db_session.query(User).filter(User.email == "unauth@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    success = promote_user_to_platform_admin_service(
        db=db_session,
        email="unauth@test.com",
        role="admin",
        confirm=True,
        operator="ops.admin@example.com",
        target_env="test",
    )
    assert success is True

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "platform.admin.promote", AuditLog.entity_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.metadata_json["action_type"] == "platform.admin.promote"
    assert audit.metadata_json["assigned_role"] == "admin"
    assert audit.metadata_json["operator"] == "ops.admin@example.com"

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


def test_bootstrap_role_change_rolled_back_if_audit_fails(db_session: Session):
    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    # Simulate audit log failure
    with patch("scripts.create_platform_admin.log_audit", side_effect=RuntimeError("Simulated audit write failure")):
        with pytest.raises(RuntimeError, match="Simulated audit write failure"):
            promote_user_to_platform_admin_service(
                db=db_session,
                email="staff@test.com",
                role="owner",
                confirm=True,
            )

    db_session.rollback()
    db_session.refresh(user)
    assert user.platform_role is None
    assert user.is_platform_admin is False


# ==============================================================================
# 6. Advisory Lock & Script-Owned Transaction Integrity Tests
# ==============================================================================

def test_bootstrap_advisory_lock_is_acquired(db_session: Session):
    with patch("scripts.create_platform_admin._acquire_admin_serialization_lock") as mock_lock:
        promote_user_to_platform_admin_service(
            db=db_session,
            email="staff@test.com",
            role="admin",
            confirm=True,
        )
        mock_lock.assert_called_once_with(db_session)


# ==============================================================================
# 7. CLI Entrypoint Tests
# ==============================================================================

def test_cli_rejects_missing_target_env_before_db():
    import sys
    from scripts.create_platform_admin import main

    test_args = ["create_platform_admin.py", "--email", "staff@test.com"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


def test_cli_dry_run_without_confirm_does_not_mutate(db_session: Session):
    import sys
    from scripts.create_platform_admin import main

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    test_args = [
        "create_platform_admin.py",
        "--target-env", "test",
        "--email", "staff@test.com",
        "--role", "owner",
    ]
    with patch.object(sys, "argv", test_args):
        with patch("scripts.create_platform_admin.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    db_session.refresh(user)
    assert user.platform_role is None
    assert user.is_platform_admin is False


def test_cli_confirm_commits_role_change(db_session: Session):
    import sys
    from scripts.create_platform_admin import main

    # Clear existing owners
    for u in db_session.query(User).filter(User.platform_role == "owner").all():
        u.platform_role = None
        u.is_platform_admin = False
    db_session.commit()

    user = db_session.query(User).filter(User.email == "staff@test.com").first()
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()

    test_args = [
        "create_platform_admin.py",
        "--target-env", "test",
        "--email", "staff@test.com",
        "--role", "owner",
        "--confirm",
        "--operator", "lead.ops@example.com",
    ]
    with patch.object(sys, "argv", test_args):
        with patch("scripts.create_platform_admin.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    db_session.refresh(user)
    assert user.platform_role == "owner"
    assert user.is_platform_admin is True

    # Cleanup
    user.platform_role = None
    user.is_platform_admin = False
    db_session.commit()


