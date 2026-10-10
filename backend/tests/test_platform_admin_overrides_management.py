import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import Feature, EntitlementOverride
from app.modules.audit.models import AuditLog


def test_override_auth_protection(client: TestClient, db_session: Session):
    biz = Business(id=uuid.uuid4(), name="Auth Test Biz C2", status="active")
    db_session.add(biz)
    db_session.commit()

    # Unauthenticated -> 401
    res = client.post(f"/api/v1/platform/businesses/{biz.id}/overrides", json={
        "feature_code": "kds.enabled",
        "override_type": "grant",
        "reason": "Unauthenticated attempt"
    })
    assert res.status_code == 401

    ov_id = uuid.uuid4()
    res_del = client.request("DELETE", f"/api/v1/platform/businesses/{biz.id}/overrides/{ov_id}", json={
        "reason": "Unauthenticated attempt"
    })
    assert res_del.status_code == 401

    # Non-platform admin -> 403
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res_forbidden = client.post(f"/api/v1/platform/businesses/{biz.id}/overrides", headers=headers, json={
        "feature_code": "kds.enabled",
        "override_type": "grant",
        "reason": "Forbidden attempt"
    })
    assert res_forbidden.status_code == 403


def test_create_override_grant_success(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    f_kds = db_session.query(Feature).filter(Feature.code == "kds.enabled").first()
    if not f_kds:
        f_kds = Feature(id=uuid.uuid4(), code="kds.enabled", name="KDS", category="kitchen")
        db_session.add(f_kds)
        db_session.commit()

    biz = Business(id=uuid.uuid4(), name="Override Grant Biz", status="active")
    db_session.add(biz)
    db_session.commit()

    future_expiry = (utc_now() + timedelta(days=10)).isoformat()

    res = client.post(
        f"/api/v1/platform/businesses/{biz.id}/overrides",
        headers=headers,
        json={
            "feature_code": "kds.enabled",
            "override_type": "grant",
            "reason": "  Promotional trial grant  ",
            "expires_at": future_expiry
        }
    )
    assert res.status_code == 200
    data = res.json()

    assert data["business_id"] == str(biz.id)
    assert data["feature_code"] == "kds.enabled"
    assert data["override_type"] == "grant"
    assert data["reason"] == "Promotional trial grant"  # trimmed
    assert data["is_active"] is True
    assert data["created_by_email"] == staff_user.email

    # Verify database persistence
    ov_in_db = db_session.query(EntitlementOverride).filter(EntitlementOverride.id == uuid.UUID(data["id"])).first()
    assert ov_in_db is not None
    assert ov_in_db.reason == "Promotional trial grant"

    # Verify audit log entry
    audit = db_session.query(AuditLog).filter(
        AuditLog.business_id == biz.id,
        AuditLog.action == "platform.entitlement.override_create"
    ).first()
    assert audit is not None
    assert audit.metadata_json["override_id"] == data["id"]
    assert audit.metadata_json["feature_code"] == "kds.enabled"


def test_create_override_outlet_scope_success(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    f_cust = db_session.query(Feature).filter(Feature.code == "ordering.customer").first()
    if not f_cust:
        f_cust = Feature(id=uuid.uuid4(), code="ordering.customer", name="Customer Ordering", category="ordering")
        db_session.add(f_cust)
        db_session.commit()

    biz = Business(id=uuid.uuid4(), name="Outlet Override Biz", status="active")
    db_session.add(biz)
    db_session.commit()

    outlet = Outlet(id=uuid.uuid4(), business_id=biz.id, name="Downtown Branch", public_slug="dt-branch")
    db_session.add(outlet)
    db_session.commit()

    res = client.post(
        f"/api/v1/platform/businesses/{biz.id}/overrides",
        headers=headers,
        json={
            "feature_code": "ordering.customer",
            "override_type": "restrict",
            "outlet_id": str(outlet.id),
            "reason": "Restricting customer ordering at Downtown branch during kitchen remodel"
        }
    )
    assert res.status_code == 200
    data = res.json()

    assert data["outlet_id"] == str(outlet.id)
    assert data["outlet_name"] == "Downtown Branch"
    assert data["override_type"] == "restrict"
    assert data["limit_value"] is None  # restrictions reset limit_value to None


def test_create_override_validation_failures(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz1 = Business(id=uuid.uuid4(), name="Validation Biz 1", status="active")
    biz2 = Business(id=uuid.uuid4(), name="Validation Biz 2", status="active")
    db_session.add_all([biz1, biz2])
    db_session.commit()

    outlet2 = Outlet(id=uuid.uuid4(), business_id=biz2.id, name="Biz 2 Outlet", public_slug="biz2-out")
    db_session.add(outlet2)
    db_session.commit()

    # 1. Empty reason -> 422
    res_reason = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/overrides",
        headers=headers,
        json={"feature_code": "kds.enabled", "override_type": "grant", "reason": "   "}
    )
    assert res_reason.status_code == 422

    # 2. Unknown feature code -> 422
    res_feat = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/overrides",
        headers=headers,
        json={"feature_code": "unknown.feature.xyz", "override_type": "grant", "reason": "Valid reason"}
    )
    assert res_feat.status_code == 422

    # 3. Cross-tenant outlet ownership -> 422
    res_cross = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/overrides",
        headers=headers,
        json={
            "feature_code": "kds.enabled",
            "override_type": "grant",
            "outlet_id": str(outlet2.id),
            "reason": "Cross tenant attempt"
        }
    )
    assert res_cross.status_code in (400, 422)

    # 4. Past expiry timestamp -> 422
    past_dt = (utc_now() - timedelta(days=1)).isoformat()
    res_exp = client.post(
        f"/api/v1/platform/businesses/{biz1.id}/overrides",
        headers=headers,
        json={
            "feature_code": "kds.enabled",
            "override_type": "grant",
            "reason": "Past expiry attempt",
            "expires_at": past_dt
        }
    )
    assert res_exp.status_code == 422


def test_revoke_override_success_and_failures(client: TestClient, db_session: Session):
    staff_user = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff_user.is_platform_admin = True
    db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(id=uuid.uuid4(), name="Revoke Test Biz", status="active")
    db_session.add(biz)
    db_session.commit()

    ov = EntitlementOverride(
        id=uuid.uuid4(),
        business_id=biz.id,
        feature_code="kds.enabled",
        override_type="grant",
        limit_value=None,
        reason="VIP temporary grant",
        created_by_user_id=staff_user.id
    )
    db_session.add(ov)
    db_session.commit()

    # 1. Empty revocation reason -> 422
    res_empty = client.request(
        "DELETE",
        f"/api/v1/platform/businesses/{biz.id}/overrides/{ov.id}",
        headers=headers,
        json={"reason": "   "}
    )
    assert res_empty.status_code == 422

    # 2. Revoke non-existent override -> 404
    fake_id = uuid.uuid4()
    res_404 = client.request(
        "DELETE",
        f"/api/v1/platform/businesses/{biz.id}/overrides/{fake_id}",
        headers=headers,
        json={"reason": "Valid reason"}
    )
    assert res_404.status_code == 404

    # 3. Successful revocation
    res_ok = client.request(
        "DELETE",
        f"/api/v1/platform/businesses/{biz.id}/overrides/{ov.id}",
        headers=headers,
        json={"reason": "Requested by owner"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "success"

    # Verify deleted from database
    ov_in_db = db_session.query(EntitlementOverride).filter(EntitlementOverride.id == ov.id).first()
    assert ov_in_db is None

    # Verify audit log entry captured original metadata
    audit = db_session.query(AuditLog).filter(
        AuditLog.business_id == biz.id,
        AuditLog.action == "platform.entitlement.override_revoke"
    ).first()
    assert audit is not None
    assert audit.metadata_json["revoked_override_id"] == str(ov.id)
    assert audit.metadata_json["reason_for_revocation"] == "Requested by owner"
    assert audit.metadata_json["original_reason"] == "VIP temporary grant"
