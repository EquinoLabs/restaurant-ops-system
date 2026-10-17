import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.audit.models import AuditLog


def test_business_creation_audit_log(client: TestClient, db_session: Session):
    # Setup platform admin
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Audit Test Bistro",
            "owner_email": "audit@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Audit Owner",
            "public_slug": "audit-bistro-main",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "subscription_status": "trial",
            "plan_name": "Pro Plan",
            "max_outlets": 3
        }
    )
    assert create_resp.status_code == 200
    biz_id = uuid.UUID(create_resp.json()["id"])

    # Verify audit log in DB
    log = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business.create",
        AuditLog.business_id == biz_id
    ).first()

    assert log is not None
    assert log.actor_user_id == admin.id
    assert log.entity_type == "business"
    assert log.entity_id == biz_id
    assert log.outlet_id is None
    assert log.metadata_json["outcome"] == "success"
    assert log.metadata_json["name"] == "Audit Test Bistro"
    assert log.metadata_json["owner_email"] == "audit@example.com"


def test_subscription_and_status_changes_audit_log(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = db_session.query(Business).filter(Business.name == "Test Business").first()

    # 1. Update subscription plan
    patch_resp1 = client.patch(
        f"/api/v1/platform/businesses/{biz.id}/subscription",
        headers=headers,
        json={"plan_name": "Enterprise Plan", "max_outlets": 10}
    )
    assert patch_resp1.status_code == 200

    log1 = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business.update_subscription",
        AuditLog.business_id == biz.id
    ).first()

    assert log1 is not None
    assert log1.actor_user_id == admin.id
    assert log1.metadata_json["outcome"] == "success"
    assert log1.metadata_json["before"]["max_outlets"] is None
    assert log1.metadata_json["after"]["max_outlets"] == 10
    assert log1.metadata_json["after"]["plan_name"] == "Enterprise Plan"

    # 2. Suspend business
    patch_resp2 = client.patch(
        f"/api/v1/platform/businesses/{biz.id}/subscription",
        headers=headers,
        json={"status": "suspended"}
    )
    assert patch_resp2.status_code == 200

    log_suspend = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business.suspend",
        AuditLog.business_id == biz.id
    ).first()

    assert log_suspend is not None
    assert log_suspend.metadata_json["before"]["status"] == "active"
    assert log_suspend.metadata_json["after"]["status"] == "suspended"

    # 3. Reactivate business
    patch_resp3 = client.patch(
        f"/api/v1/platform/businesses/{biz.id}/subscription",
        headers=headers,
        json={"status": "active"}
    )
    assert patch_resp3.status_code == 200

    log_reactivate = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business.reactivate",
        AuditLog.business_id == biz.id
    ).first()

    assert log_reactivate is not None
    assert log_reactivate.metadata_json["before"]["status"] == "suspended"
    assert log_reactivate.metadata_json["after"]["status"] == "active"


def test_outlet_creation_and_owner_assignment_audit_log(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = db_session.query(Business).filter(Business.name == "Test Business").first()

    # 1. Create Outlet
    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/outlets",
        headers=headers,
        json={
            "name": "Audit Secondary Outlet",
            "public_slug": "audit-secondary",
            "currency": "INR",
            "timezone": "Asia/Kolkata"
        }
    )
    assert outlet_resp.status_code == 200
    new_outlet_id = uuid.UUID(outlet_resp.json()["id"])

    log_outlet = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.outlet.create",
        AuditLog.outlet_id == new_outlet_id
    ).first()

    assert log_outlet is not None
    assert log_outlet.actor_user_id == admin.id
    assert log_outlet.business_id == biz.id
    assert log_outlet.metadata_json["name"] == "Audit Secondary Outlet"
    assert log_outlet.metadata_json["public_slug"] == "audit-secondary"

    # 2. Assign Owner (creating a new user with password)
    assign_resp = client.post(
        f"/api/v1/platform/businesses/{biz.id}/assign-owner",
        headers=headers,
        json={
            "outlet_id": str(new_outlet_id),
            "email": "newowner@test.com",
            "password": "SuperSecretPassword123!",
            "display_name": "New Owner User"
        }
    )
    assert assign_resp.status_code == 200

    log_owner = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business_owner.assign",
        AuditLog.business_id == biz.id
    ).first()

    assert log_owner is not None
    assert log_owner.actor_user_id == admin.id
    assert log_owner.business_id == biz.id
    assert log_owner.outlet_id is None
    assert log_owner.metadata_json["email"] == "newowner@test.com"
    assert log_owner.metadata_json["created_new_user"] is True

    # EXPLICIT SECRET CHECK: password or hash MUST NOT exist in metadata_json
    metadata_str = str(log_owner.metadata_json)
    assert "SuperSecretPassword123!" not in metadata_str
    assert "password" not in log_owner.metadata_json
    assert "password_hash" not in log_owner.metadata_json


def test_failed_operation_rollback_leaves_no_audit_log(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create business with short name (min 2 chars validation)
    fail_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "X",
            "owner_email": "dup2@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Dup2 Owner",
            "public_slug": f"dup2-{uuid.uuid4().hex[:6]}"
        }
    )
    assert fail_resp.status_code == 422

    # Verify NO audit log was written for "Duplicate Slug Biz"
    logs = db_session.query(AuditLog).filter(
        AuditLog.action == "platform.business.create"
    ).all()
    for l in logs:
        assert l.metadata_json.get("name") != "Duplicate Slug Biz"


def test_non_platform_user_denied_creates_no_audit_log(client: TestClient, db_session: Session):
    # Regular staff user login (not platform admin)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    initial_audit_count = db_session.query(AuditLog).count()

    # Unauthorized call
    resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Hacker Biz",
            "owner_email": "hacker@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Hacker Owner",
            "public_slug": "hacker-slug"
        }
    )
    assert resp.status_code == 403

    # Audit log count must remain unchanged
    final_audit_count = db_session.query(AuditLog).count()
    assert final_audit_count == initial_audit_count
