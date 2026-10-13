import pytest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User, OutletMembership
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog
from app.core.security import hash_password, verify_password, create_access_token
from app.core.errors import NotFoundError, ValidationError
from scripts.break_glass_recovery import (
    diagnose_platform_state,
    execute_break_glass_recovery,
    validate_recovery_database_target,
    main as cli_main,
)


def _setup_recovery_test_users(db_session: Session):
    """Helper to set up platform governance test users."""
    # Active Platform Owner
    owner = db_session.query(User).filter(User.email == "staff@test.com").first()
    owner.platform_role = "owner"
    owner.is_platform_admin = True
    owner.status = "active"
    owner.password_hash = hash_password("OwnerPassword123!")

    # Active Platform Admin (designated successor)
    admin = db_session.query(User).filter(User.email == "admin_test@test.com").first()
    if not admin:
        admin = User(
            email="admin_test@test.com",
            display_name="Test Admin Successor",
            password_hash=hash_password("AdminPassword123!"),
            status="active",
            is_platform_admin=True,
            platform_role="admin",
        )
        db_session.add(admin)
    else:
        admin.platform_role = "admin"
        admin.is_platform_admin = True
        admin.status = "active"
        admin.password_hash = hash_password("AdminPassword123!")

    # Active Platform Operator
    operator = db_session.query(User).filter(User.email == "operator_test@test.com").first()
    if not operator:
        operator = User(
            email="operator_test@test.com",
            display_name="Test Operator",
            password_hash=hash_password("OperatorPassword123!"),
            status="active",
            is_platform_admin=False,
            platform_role="operator",
        )
        db_session.add(operator)
    else:
        operator.platform_role = "operator"
        operator.is_platform_admin = False
        operator.status = "active"
        operator.password_hash = hash_password("OperatorPassword123!")

    # Regular user (unauth@test.com)
    regular = db_session.query(User).filter(User.email == "unauth@test.com").first()
    regular.platform_role = None
    regular.is_platform_admin = False
    regular.status = "active"
    regular.password_hash = hash_password("RegularPassword123!")

    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(admin)
    db_session.refresh(operator)
    db_session.refresh(regular)
    return owner, admin, operator, regular


# ==============================================================================
# 1. Stage A: Diagnostic Inspection (Read-Only)
# ==============================================================================

def test_diagnose_healthy_platform(db_session: Session):
    owner, admin, operator, _ = _setup_recovery_test_users(db_session)

    report = diagnose_platform_state(db_session)
    assert report["health_status"] == "HEALTHY"
    assert report["governance_operational"] is True
    assert len(report["active_owners"]) == 1
    assert report["active_owners"][0]["email"] == owner.email
    assert len(report["suspended_owners"]) == 0
    assert report["active_admins_count"] >= 1
    assert report["active_operators_count"] >= 1


def test_diagnose_zero_owner_orphaned(db_session: Session):
    owner, _, _, _ = _setup_recovery_test_users(db_session)
    # Demote owner to admin to simulate orphaned governance
    owner.platform_role = "admin"
    db_session.commit()

    report = diagnose_platform_state(db_session)
    assert report["health_status"] == "ZERO_OWNER_ORPHANED"
    assert report["governance_operational"] is False
    assert len(report["active_owners"]) == 0
    assert len(report["suspended_owners"]) == 0


def test_diagnose_owner_suspended(db_session: Session):
    owner, _, _, _ = _setup_recovery_test_users(db_session)
    # Suspend owner
    owner.status = "suspended"
    db_session.commit()

    report = diagnose_platform_state(db_session)
    assert report["health_status"] == "OWNER_SUSPENDED"
    assert report["governance_operational"] is False
    assert len(report["active_owners"]) == 0
    assert len(report["suspended_owners"]) == 1
    assert report["suspended_owners"][0]["email"] == owner.email


def test_diagnose_multiple_owners_anomalous(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)
    # Set admin to owner as well (data anomaly)
    admin.platform_role = "owner"
    db_session.commit()

    report = diagnose_platform_state(db_session)
    assert report["health_status"] == "ANOMALOUS_MULTIPLE_OWNERS"
    assert report["governance_operational"] is False
    assert len(report["active_owners"]) == 2


# ==============================================================================
# 2. Stage B: Authorization Gates & Fail-Closed Behavior
# ==============================================================================

def test_recovery_missing_operator_fails_closed(db_session: Session):
    _setup_recovery_test_users(db_session)

    with pytest.raises(ValidationError, match="Operator identity .* is required"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="",
            incident_ref="INC-1001",
            target_identifier="admin_test@test.com",
            confirm=True,
        )


def test_recovery_missing_incident_ref_fails_closed(db_session: Session):
    _setup_recovery_test_users(db_session)

    with pytest.raises(ValidationError, match="incident/change reference .* is required"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="",
            target_identifier="admin_test@test.com",
            confirm=True,
        )


def test_recovery_missing_target_fails_closed(db_session: Session):
    _setup_recovery_test_users(db_session)

    with pytest.raises(ValidationError, match="Target user .* is required"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier="",
            confirm=True,
        )


def test_recovery_nonexistent_target_fails_closed(db_session: Session):
    _setup_recovery_test_users(db_session)

    fake_email = "nonexistent_target_user@test.com"
    with pytest.raises(NotFoundError, match=fake_email):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=fake_email,
            confirm=True,
        )


def test_dry_run_without_confirm_writes_nothing(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    res = execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier="admin_test@test.com",
        confirm=False,  # Dry-run!
    )
    assert res["stage"] == "B_AUTHORIZE_DRY_RUN"
    assert res["dry_run"] is True
    assert "Zero changes were written" in res["message"]

    # Verify database state was NOT mutated
    db_session.refresh(owner)
    db_session.refresh(admin)
    assert owner.platform_role == "owner"
    assert admin.platform_role == "admin"


# ==============================================================================
# 3. Stage C: Recovery Operations (replace-owner, reactivate-owner, reset-credentials)
# ==============================================================================

def test_replace_owner_success(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    res = execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier=admin.email,
        confirm=True,
    )
    assert res["stage"] == "D_VERIFY_AND_CLOSE"
    assert res["outcome"] == "success"
    assert res["target"]["role"] == "owner"
    assert res["active_owner_count"] == 1
    assert res["previous_owner"]["id"] == str(owner.id)

    # DB verification
    db_session.refresh(owner)
    db_session.refresh(admin)
    assert owner.platform_role == "admin"
    assert owner.is_platform_admin is True
    assert admin.platform_role == "owner"
    assert admin.is_platform_admin is True

    # Audit log verification
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.recovery.break_glass",
        AuditLog.entity_id == admin.id,
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.metadata_json["operator"] == "alice.ops"
    assert audit.metadata_json["incident_ref"] == "INC-1001"
    assert audit.metadata_json["action_type"] == "replace-owner"
    assert audit.metadata_json["new_platform_role"] == "owner"
    assert audit.metadata_json["previous_owner"]["email"] == owner.email


def test_replace_owner_fails_if_target_is_not_admin(db_session: Session):
    _, _, operator, regular = _setup_recovery_test_users(db_session)

    # 1. Attempting with regular user -> rejected
    with pytest.raises(ValidationError, match="must be an active Platform Administrator"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=regular.email,
            confirm=True,
        )

    # 2. Attempting with operator -> rejected
    with pytest.raises(ValidationError, match="must be an active Platform Administrator"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=operator.email,
            confirm=True,
        )


def test_replace_owner_fails_if_target_is_suspended(db_session: Session):
    _, admin, _, _ = _setup_recovery_test_users(db_session)
    admin.status = "suspended"
    db_session.commit()

    with pytest.raises(ValidationError, match="Target account must be active"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=admin.email,
            confirm=True,
        )


def test_replace_owner_noop_if_target_already_owner(db_session: Session):
    owner, _, _, _ = _setup_recovery_test_users(db_session)

    res = execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier=owner.email,
        confirm=True,
    )
    assert res["outcome"] == "noop"
    assert "already the active Platform Owner" in res["message"]


def test_reactivate_owner_success(db_session: Session):
    owner, _, _, _ = _setup_recovery_test_users(db_session)
    owner.status = "suspended"
    db_session.commit()

    res = execute_break_glass_recovery(
        db=db_session,
        action="reactivate-owner",
        operator="alice.ops",
        incident_ref="INC-1002",
        target_identifier=owner.email,
        confirm=True,
    )
    assert res["stage"] == "D_VERIFY_AND_CLOSE"
    assert res["outcome"] == "success"

    db_session.refresh(owner)
    assert owner.status == "active"
    assert owner.platform_role == "owner"


def test_reactivate_owner_fails_for_non_owner(db_session: Session):
    _, admin, _, _ = _setup_recovery_test_users(db_session)
    admin.status = "suspended"
    db_session.commit()

    with pytest.raises(ValidationError, match="only applies to Platform Owners"):
        execute_break_glass_recovery(
            db=db_session,
            action="reactivate-owner",
            operator="alice.ops",
            incident_ref="INC-1002",
            target_identifier=admin.email,
            confirm=True,
        )


def test_reset_credentials_operation_is_disabled(db_session: Session):
    owner, _, _, _ = _setup_recovery_test_users(db_session)

    with pytest.raises(ValidationError, match="reset-credentials.*disabled"):
        execute_break_glass_recovery(
            db=db_session,
            action="reset-credentials",
            operator="alice.ops",
            incident_ref="INC-1003",
            target_identifier=owner.email,
            confirm=True,
        )


def test_new_password_argument_is_rejected(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    with pytest.raises(ValidationError, match="Argument 'new_password' is not supported"):
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=admin.email,
            new_password="AnyPassword123!",
            confirm=True,
        )


def test_incident_reference_regex_validation(db_session: Session):
    _, admin, _, _ = _setup_recovery_test_users(db_session)

    # Invalid formats rejected
    for invalid_ref in ["ticket-1001", "12345", "INCIDENT", "foo", ""]:
        with pytest.raises(ValidationError, match="incident"):
            execute_break_glass_recovery(
                db=db_session,
                action="replace-owner",
                operator="alice.ops",
                incident_ref=invalid_ref,
                target_identifier=admin.email,
                confirm=False,
            )

    # Valid formats accepted
    for valid_ref in ["INC-1001", "inc-9999", "CHG-4040", "ROMS-1234"]:
        res = execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref=valid_ref,
            target_identifier=admin.email,
            confirm=False,
        )
        assert res["outcome"] == "dry_run_completed"


def test_audit_metadata_includes_supplementary_os_context(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    res = execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-48201",
        target_identifier=admin.email,
        confirm=True,
    )
    assert res["outcome"] == "success"

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.recovery.break_glass",
        AuditLog.entity_id == admin.id,
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert "operator_system_user" in audit.metadata_json
    assert audit.metadata_json["operator_system_user"] is not None
    assert "execution_host" in audit.metadata_json
    assert audit.metadata_json["execution_host"] is not None


# ==============================================================================
# 3b. Target Environment Hardening & Pre-DB Verification
# ==============================================================================

def test_validate_target_env_missing_fails_closed():
    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_recovery_database_target(None)

    with pytest.raises(ValidationError, match="Target environment .* is required"):
        validate_recovery_database_target("   ")


def test_validate_target_env_invalid_fails_closed():
    with pytest.raises(ValidationError, match="Invalid target environment"):
        validate_recovery_database_target("qa_custom_env")


def test_validate_target_env_production_with_implicit_fallback_fails_closed():
    with pytest.raises(ValidationError, match="requires an explicitly configured DATABASE_URL"):
        validate_recovery_database_target(
            target_env="production",
            database_uri="postgresql+psycopg://roms_user:pass@localhost:5432/roms_db",
            explicit_database_url=None,  # Implicit fallback!
        )


def test_validate_target_env_production_with_localhost_fails_closed():
    with pytest.raises(ValidationError, match="cannot target a localhost/loopback database"):
        validate_recovery_database_target(
            target_env="production",
            database_uri="postgresql+psycopg://roms_user:pass@localhost:5432/roms_db",
            explicit_database_url="postgresql+psycopg://roms_user:pass@localhost:5432/roms_db",
        )


def test_validate_target_env_local_with_remote_host_fails_closed():
    with pytest.raises(ValidationError, match="Target environment mismatch"):
        validate_recovery_database_target(
            target_env="local",
            database_uri="postgresql+psycopg://user:pass@ep-remote.neon.tech:5432/neondb",
            explicit_database_url="postgresql+psycopg://user:pass@ep-remote.neon.tech:5432/neondb",
        )


def test_validate_target_env_masks_credentials_securely():
    res = validate_recovery_database_target(
        target_env="production",
        database_uri="postgresql+psycopg://admin_user:SuperSecretPassword123@ep-remote.neon.tech:5432/prod_db",
        explicit_database_url="postgresql+psycopg://admin_user:SuperSecretPassword123@ep-remote.neon.tech:5432/prod_db",
    )
    assert res["target_env"] == "production"
    assert res["host"] == "ep-remote.neon.tech"
    assert res["port"] == 5432
    assert res["database"] == "prod_db"
    assert "SuperSecretPassword123" not in res["masked_uri"]
    assert ":****@" in res["masked_uri"]


def test_cli_rejects_missing_target_env_before_db():
    with patch("sys.argv", ["break_glass_recovery.py", "--diagnose"]):
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        # Argparse exits code 2 when required argument is omitted
        assert exc_info.value.code == 2


def test_cli_rejects_unsupported_reset_credentials_action_before_db():
    with patch("sys.argv", ["break_glass_recovery.py", "--target-env", "local", "--action", "reset-credentials"]):
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        assert exc_info.value.code == 2


def test_cli_rejects_removed_new_password_argument_before_db():
    with patch("sys.argv", [
        "break_glass_recovery.py",
        "--target-env", "local",
        "--action", "diagnose",
        "--new-password", "SomePassword123!"
    ]):
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        assert exc_info.value.code == 2


# ==============================================================================
# 3c. JWT Authentication & Role Demotion / Suspension Behavior (OP03-SEC-02)
# ==============================================================================

def test_jwt_demoted_owner_loses_owner_routes_immediately(db_session: Session, client: TestClient):
    owner, admin, operator, _ = _setup_recovery_test_users(db_session)
    predecessor_token = create_access_token(subject=str(owner.id))
    headers = {"Authorization": f"Bearer {predecessor_token}"}

    # 1. Prior to recovery, Owner token accesses Owner-only endpoint (POST /api/v1/platform/users/{id}/suspend)
    r1 = client.post(f"/api/v1/platform/users/{operator.id}/suspend", headers=headers)
    assert r1.status_code == 200

    # Reset operator status for next check
    operator.status = "active"
    db_session.commit()

    # 2. Execute break-glass replace-owner
    execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier=admin.email,
        confirm=True,
    )
    db_session.commit()

    # 3. Using the EXACT SAME pre-issued token, Owner-only routes are now rejected with HTTP 403 Forbidden
    r2 = client.post(f"/api/v1/platform/users/{operator.id}/suspend", headers=headers)
    assert r2.status_code == 403

    # 4. Residual risk demonstration: Predecessor was demoted to 'admin', so admin routes still succeed
    r3 = client.get("/api/v1/platform/businesses", headers=headers)
    assert r3.status_code == 200


def test_jwt_suspended_predecessor_loses_all_access_immediately(db_session: Session, client: TestClient):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)
    predecessor_token = create_access_token(subject=str(owner.id))
    headers = {"Authorization": f"Bearer {predecessor_token}"}

    # 1. Execute break-glass replace-owner
    execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier=admin.email,
        confirm=True,
    )
    # 2. Suspend predecessor (approved compromise workflow)
    owner.status = "suspended"
    db_session.commit()

    # 3. Predecessor token is now rejected with HTTP 401 across ALL endpoints
    r_admin = client.get("/api/v1/platform/businesses", headers=headers)
    assert r_admin.status_code == 401
    assert "inactive" in str(r_admin.json()).lower()


# ==============================================================================
# 4. Invariant Preservation, Advisory Locking & Rollback Safety
# ==============================================================================

def test_recovery_invokes_advisory_lock(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    with patch("scripts.break_glass_recovery._acquire_admin_serialization_lock") as mock_lock:
        execute_break_glass_recovery(
            db=db_session,
            action="replace-owner",
            operator="alice.ops",
            incident_ref="INC-1001",
            target_identifier=admin.email,
            confirm=True,
        )
        mock_lock.assert_called_once_with(db_session)


def test_tenant_memberships_preserved_across_recovery(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    outlet = db_session.query(Outlet).first()
    assert outlet is not None

    mem = OutletMembership(user_id=admin.id, outlet_id=outlet.id, role="manager")
    db_session.add(mem)
    db_session.commit()

    # Execute recovery replacing owner with admin
    execute_break_glass_recovery(
        db=db_session,
        action="replace-owner",
        operator="alice.ops",
        incident_ref="INC-1001",
        target_identifier=admin.email,
        confirm=True,
    )

    db_session.refresh(admin)
    assert len(admin.memberships) == 1
    assert admin.memberships[0].role == "manager"
    assert admin.memberships[0].outlet_id == outlet.id


def test_rollback_on_audit_failure(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)

    with patch("scripts.break_glass_recovery.log_audit", side_effect=RuntimeError("Audit disk full")):
        with pytest.raises(RuntimeError, match="Audit disk full"):
            execute_break_glass_recovery(
                db=db_session,
                action="replace-owner",
                operator="alice.ops",
                incident_ref="INC-1001",
                target_identifier=admin.email,
                confirm=True,
            )

        db_session.rollback()
        db_session.refresh(owner)
        db_session.refresh(admin)
        assert owner.platform_role == "owner"
        assert admin.platform_role == "admin"


def test_post_verification_fails_if_multiple_owners_remain(db_session: Session):
    owner, admin, _, _ = _setup_recovery_test_users(db_session)
    from sqlalchemy.orm import Query

    # Simulate anomalous post-verification returning 2 active owners
    original_all = Query.all
    call_count = [0]

    def mock_all(self):
        call_count[0] += 1
        # The post verification query is the final .all() call
        if call_count[0] >= 3:
            return [owner, admin]
        return original_all(self)

    with patch.object(Query, "all", side_effect=mock_all, autospec=True):
        with pytest.raises(RuntimeError, match="Post-recovery invariant violation"):
            execute_break_glass_recovery(
                db=db_session,
                action="replace-owner",
                operator="alice.ops",
                incident_ref="INC-1001",
                target_identifier=admin.email,
                confirm=True,
            )
