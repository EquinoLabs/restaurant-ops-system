import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.audit.models import AuditLog
from app.modules.audit.service import log_audit


def test_platform_audit_logs_api_authorization(client: TestClient, db_session: Session):
    # Unauthenticated request -> 401
    resp_unauth = client.get("/api/v1/platform/audit-logs")
    assert resp_unauth.status_code == 401

    # Non-platform admin -> 403
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff.is_platform_admin = False
    db_session.commit()

    login_staff = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    staff_token = login_staff.json()["access_token"]
    resp_forbidden = client.get(
        "/api/v1/platform/audit-logs",
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert resp_forbidden.status_code == 403


def test_platform_audit_logs_api_listing_and_filtering(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = db_session.query(Business).first()

    # Create dummy audit logs
    log1 = log_audit(
        db=db_session,
        business_id=biz.id,
        actor_user_id=admin.id,
        action="platform.business.create",
        entity_type="business",
        entity_id=biz.id,
        metadata_json={"outcome": "success", "name": biz.name}
    )
    log2 = log_audit(
        db=db_session,
        business_id=None,
        actor_user_id=admin.id,
        action="platform.admin.grant",
        entity_type="user",
        entity_id=admin.id,
        metadata_json={"outcome": "success", "target_email": admin.email}
    )
    db_session.commit()

    # 1. Fetch all audit logs
    resp_all = client.get("/api/v1/platform/audit-logs", headers=headers)
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert "items" in data_all
    assert "total" in data_all
    assert data_all["total"] >= 2

    # Verify fields in items
    items = data_all["items"]
    assert len(items) > 0
    first_item = items[0]
    assert "id" in first_item
    assert "action" in first_item
    assert "entity_type" in first_item
    assert "created_at" in first_item

    # 2. Filter by action
    resp_action = client.get(
        "/api/v1/platform/audit-logs?action=platform.admin.grant",
        headers=headers
    )
    assert resp_action.status_code == 200
    data_action = resp_action.json()
    assert all(item["action"] == "platform.admin.grant" for item in data_action["items"])

    # 3. Filter by business_id
    resp_biz = client.get(
        f"/api/v1/platform/audit-logs?business_id={biz.id}",
        headers=headers
    )
    assert resp_biz.status_code == 200
    data_biz = resp_biz.json()
    assert all(item["business_id"] == str(biz.id) for item in data_biz["items"])

    # 4. System-level log with null business_id appears when no business filter supplied
    sys_log_present = any(item["business_id"] is None for item in data_all["items"])
    assert sys_log_present is True


def test_platform_audit_logs_pagination_and_null_handling(client: TestClient, db_session: Session):
    admin = db_session.query(User).filter(User.email == "staff@test.com").first()
    admin.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Log entry with null actor and null business/outlet
    null_log = log_audit(
        db=db_session,
        business_id=None,
        outlet_id=None,
        actor_user_id=None,
        action="platform.system.test",
        entity_type="system",
        entity_id=uuid.uuid4(),
        metadata_json=None
    )
    db_session.commit()

    resp = client.get("/api/v1/platform/audit-logs?limit=1&offset=0", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert len(data["items"]) == 1

    # Test ordering (newest first)
    items = data["items"]
    assert items[0]["action"] == "platform.system.test"
    assert items[0]["actor_user_id"] is None
    assert items[0]["actor_display_name"] is None
    assert items[0]["business_name"] is None
