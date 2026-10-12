import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.base import utc_now
from app.modules.staff.models import User
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.subscriptions.models import (
    Plan, Feature, PlanFeature, BusinessSubscription
)
from app.modules.subscriptions.service import (
    EntitlementService, compute_annual_period_end, ensure_utc
)
from app.modules.audit.models import AuditLog


def get_admin_headers(client: TestClient, db_session: Session) -> dict:
    staff = db_session.query(User).filter(User.email == "staff@test.com").first()
    staff.is_platform_admin = True
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@test.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_calendar_arithmetic_utilities():
    # 1. Standard non-leap term
    dt1 = datetime(2023, 5, 15, 10, 30, 0, tzinfo=timezone.utc)
    res1 = compute_annual_period_end(dt1)
    assert res1 == datetime(2024, 5, 15, 10, 30, 0, tzinfo=timezone.utc)

    # 2. Leap day start: 2024-02-29 -> 2025-02-28
    dt_leap = datetime(2024, 2, 29, 14, 0, 0, tzinfo=timezone.utc)
    res_leap = compute_annual_period_end(dt_leap)
    assert res_leap == datetime(2025, 2, 28, 14, 0, 0, tzinfo=timezone.utc)

    # 3. Non-leap Feb 28 -> Feb 28 in leap year
    dt_feb28 = datetime(2023, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    res_feb28 = compute_annual_period_end(dt_feb28)
    assert res_feb28 == datetime(2024, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

    # 4. Month-end: 2024-01-31 -> 2025-01-31
    dt_jan31 = datetime(2024, 1, 31, 0, 0, 0, tzinfo=timezone.utc)
    res_jan31 = compute_annual_period_end(dt_jan31)
    assert res_jan31 == datetime(2025, 1, 31, 0, 0, 0, tzinfo=timezone.utc)

    # 5. Leap year spanning term (366 days elapsed)
    dt_span = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    res_span = compute_annual_period_end(dt_span)
    assert res_span == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert (res_span - dt_span).days == 366


def test_provisioning_initializes_30_day_trial(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Trial Provisioning Cafe",
            "primary_outlet_name": "Trial Main",
            "public_slug": f"trial-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    assert res.status_code == 200
    biz_data = res.json()
    biz_id = biz_data["id"]

    biz = db_session.query(Business).filter(Business.id == uuid.UUID(biz_id)).first()
    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == uuid.UUID(biz_id),
        BusinessSubscription.is_current == True
    ).first()

    assert biz.subscription_status == "trial"
    assert sub.status == "trial"
    assert biz.trial_ends_at is not None
    assert sub.trial_ends_at == biz.trial_ends_at

    # Exact 30-day difference from creation
    diff = biz.trial_ends_at - biz.created_at
    assert abs(diff.total_seconds() - (30 * 86400)) < 5


def test_annual_term_exact_validation(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Validation Cafe",
            "primary_outlet_name": "Validation Main",
            "public_slug": f"val-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    start = utc_now()
    exact_end = compute_annual_period_end(start)

    # 1. Shorter term (< 1 calendar year) -> 422
    shorter_end = exact_end - timedelta(days=10)
    res_short = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "growth_pos",
            "current_period_start": start.isoformat(),
            "current_period_end": shorter_end.isoformat(),
        }
    )
    assert res_short.status_code == 422
    assert "must be exactly one calendar year" in res_short.json()["detail"]["error"]["message"]

    # 2. Longer term (> 1 calendar year) -> 422
    longer_end = exact_end + timedelta(days=10)
    res_long = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "growth_pos",
            "current_period_start": start.isoformat(),
            "current_period_end": longer_end.isoformat(),
        }
    )
    assert res_long.status_code == 422
    assert "must be exactly one calendar year" in res_long.json()["detail"]["error"]["message"]

    # 3. Exact term -> 200 OK
    res_ok = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "growth_pos",
            "current_period_start": start.isoformat(),
            "current_period_end": exact_end.isoformat(),
        }
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["subscription_status"] == "active"


def test_trial_conversion_starts_immediately_and_retains_history(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Conversion Cafe",
            "primary_outlet_name": "Conv Main",
            "public_slug": f"conv-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Convert trial to paid without passing start/end (defaults to now and 1 year)
    res_conv = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "growth_pos"
        }
    )
    assert res_conv.status_code == 200

    # Inspect history: prior trial row retained as is_current=False
    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).order_by(BusinessSubscription.created_at.desc()).all()

    assert len(subs) == 2
    curr = [s for s in subs if s.is_current][0]
    hist = [s for s in subs if not s.is_current][0]

    assert hist.status == "trial"
    assert hist.trial_ends_at is not None

    assert curr.status == "active"
    assert curr.trial_ends_at is None
    assert curr.current_period_start is not None
    assert ensure_utc(curr.current_period_end) == compute_annual_period_end(ensure_utc(curr.current_period_start))


def test_timely_renewal_preserves_anniversary(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Renewal Cafe",
            "primary_outlet_name": "Renew Main",
            "public_slug": f"renew-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Activate
    start1 = utc_now()
    end1 = compute_annual_period_end(start1)
    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "starter_pos",
            "current_period_start": start1.isoformat(),
            "current_period_end": end1.isoformat(),
        }
    )

    # Timely renewal while active
    res_renew = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "renew"}
    )
    assert res_renew.status_code == 200

    # Verify complete subscription history
    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).order_by(BusinessSubscription.created_at.asc()).all()

    # Setup: 1 trial + 1 initial annual paid term + 1 timely renewal = 3 total records
    assert len(subs) == 3

    trial_sub, initial_sub, renewed_sub = subs[0], subs[1], subs[2]

    # 1. Original trial record remains in history
    assert trial_sub.status == "trial"
    assert trial_sub.is_current is False
    assert trial_sub.trial_ends_at is not None

    # 2. Initial paid annual record is preserved with original dates and is_current=False
    assert initial_sub.status == "active"
    assert initial_sub.is_current is False
    assert ensure_utc(initial_sub.current_period_start) == ensure_utc(start1)
    assert ensure_utc(initial_sub.current_period_end) == ensure_utc(end1)

    # 3. Renewed record has start == prior end, end == compute_annual_period_end(new_start)
    expected_renew_end = compute_annual_period_end(end1)
    assert renewed_sub.status == "active"
    assert renewed_sub.is_current is True
    assert ensure_utc(renewed_sub.current_period_start) == ensure_utc(end1)
    assert ensure_utc(renewed_sub.current_period_end) == expected_renew_end

    # 4. Renewed record is the only current subscription
    current_subs = [s for s in subs if s.is_current]
    assert len(current_subs) == 1
    assert current_subs[0].id == renewed_sub.id


def test_consecutive_timely_renewals_preserve_history_and_anniversaries(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Multi Renewal Cafe",
            "primary_outlet_name": "Multi Renew Main",
            "public_slug": f"multi-renew-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Initial activation (Year 1)
    start1 = utc_now()
    end1 = compute_annual_period_end(start1)
    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "starter_pos",
            "current_period_start": start1.isoformat(),
            "current_period_end": end1.isoformat(),
        }
    )

    # First renewal (Year 2)
    res_renew1 = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "renew"}
    )
    assert res_renew1.status_code == 200

    # Second renewal (Year 3)
    res_renew2 = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "renew"}
    )
    assert res_renew2.status_code == 200

    # Query all historical records in order
    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).order_by(BusinessSubscription.created_at.asc()).all()

    # Total: 1 trial + 3 annual paid terms = 4 records
    assert len(subs) == 4

    trial_sub = subs[0]
    term1 = subs[1]
    term2 = subs[2]
    term3 = subs[3]

    # Verify trial record
    assert trial_sub.status == "trial"
    assert trial_sub.is_current is False

    # Verify Year 1 record
    assert term1.status == "active"
    assert term1.is_current is False
    assert ensure_utc(term1.current_period_start) == ensure_utc(start1)
    assert ensure_utc(term1.current_period_end) == ensure_utc(end1)

    # Verify Year 2 record
    expected_end2 = compute_annual_period_end(end1)
    assert term2.status == "active"
    assert term2.is_current is False
    assert ensure_utc(term2.current_period_start) == ensure_utc(end1)
    assert ensure_utc(term2.current_period_end) == expected_end2

    # Verify Year 3 record
    expected_end3 = compute_annual_period_end(expected_end2)
    assert term3.status == "active"
    assert term3.is_current is True
    assert ensure_utc(term3.current_period_start) == expected_end2
    assert ensure_utc(term3.current_period_end) == expected_end3

    # Invariant: exactly one current subscription record
    current_subs = [s for s in subs if s.is_current]
    assert len(current_subs) == 1
    assert current_subs[0].id == term3.id


def test_late_renewal_after_expiry_requires_new_term(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Late Cafe",
            "primary_outlet_name": "Late Main",
            "public_slug": f"late-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Sub in past (expired)
    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id,
        BusinessSubscription.is_current == True
    ).first()
    sub.status = "active"
    sub.current_period_start = utc_now() - timedelta(days=400)
    sub.current_period_end = utc_now() - timedelta(days=35)
    db_session.commit()

    # Renew late -> creates new term starting at now
    res_renew = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "renew", "plan_code": "pro_kds"}
    )
    assert res_renew.status_code == 200

    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).all()
    assert len(subs) == 2
    curr = [s for s in subs if s.is_current][0]
    assert curr.status == "active"
    assert ensure_utc(curr.current_period_end) > utc_now()


def test_midterm_plan_switch_preserves_renewal_date(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Switch Cafe",
            "primary_outlet_name": "Switch Main",
            "public_slug": f"switch-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    start = utc_now()
    end = compute_annual_period_end(start)
    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "starter_pos",
            "current_period_start": start.isoformat(),
            "current_period_end": end.isoformat(),
        }
    )

    # Mid-term switch to growth_pos
    res_switch = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "change_plan",
            "plan_code": "growth_pos"
        }
    )
    assert res_switch.status_code == 200

    curr = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id,
        BusinessSubscription.is_current == True
    ).first()
    plan = db_session.query(Plan).filter(Plan.id == curr.plan_id).first()
    assert plan.code == "growth_pos"
    assert ensure_utc(curr.current_period_start) == start
    assert ensure_utc(curr.current_period_end) == end


def test_scheduled_cancellation_and_revocation(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Cancel Cafe",
            "primary_outlet_name": "Cancel Main",
            "public_slug": f"cancel-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Activate
    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "starter_pos"}
    )

    # 1. Schedule cancellation
    res_sched = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "schedule_cancellation"}
    )
    assert res_sched.status_code == 200

    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id,
        BusinessSubscription.is_current == True
    ).first()
    assert sub.cancel_at_period_end is True
    assert sub.cancelled_at is not None
    assert sub.status == "active"

    # Operational access is preserved while before period end
    ent = EntitlementService.check_entitlement(db_session, biz_id, "ordering.staff")
    assert ent.authorized is True
    assert ent.resolved_status == "active"

    # 2. Revoke scheduled cancellation
    res_revoke = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "revoke_scheduled_cancellation"}
    )
    assert res_revoke.status_code == 200

    db_session.refresh(sub)
    assert sub.cancel_at_period_end is False
    assert sub.cancelled_at is None


def test_immediate_cancellation_flow(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Immediate Cafe",
            "primary_outlet_name": "Imm Main",
            "public_slug": f"imm-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Immediate cancel without reason -> 422
    res_no_reason = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "cancel_immediately", "reason": "   "}
    )
    assert res_no_reason.status_code == 422

    # Immediate cancel with reason -> 200
    res_cancel = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "cancel_immediately", "reason": "Non-payment violation"}
    )
    assert res_cancel.status_code == 200

    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id,
        BusinessSubscription.is_current == True
    ).first()
    assert sub.status == "cancelled"
    assert sub.cancelled_at is not None

    # Operational access revoked immediately
    ent = EntitlementService.check_entitlement(db_session, biz_id, "ordering.staff")
    assert ent.authorized is False
    assert ent.reason == "SUBSCRIPTION_CANCELLED"

    # Read-only menu permitted for active business
    ent_menu = EntitlementService.check_entitlement(db_session, biz_id, "menu.digital")
    assert ent_menu.authorized is True


def test_past_due_preserves_period_end_and_extension(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "PastDue Cafe",
            "primary_outlet_name": "PD Main",
            "public_slug": f"pd-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])
    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "starter_pos"}
    )

    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id,
        BusinessSubscription.is_current == True
    ).first()
    orig_end = sub.current_period_end

    # Mark past due -> period end preserved
    res_pd = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "mark_past_due"}
    )
    assert res_pd.status_code == 200
    db_session.refresh(sub)
    assert sub.status == "past_due"
    assert ensure_utc(sub.current_period_end) == ensure_utc(orig_end)

    # Authorized recovery extension
    new_deadline = utc_now() + timedelta(days=14)
    res_ext = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "mark_past_due_with_extension",
            "current_period_end": new_deadline.isoformat(),
            "reason": "Payment recovery promise to pay by next week"
        }
    )
    assert res_ext.status_code == 200
    db_session.refresh(sub)
    assert abs((ensure_utc(sub.current_period_end) - new_deadline).total_seconds()) < 5


def test_canonical_plans_and_history_endpoints(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    # 1. GET /platform/plans
    res_plans = client.get("/api/v1/platform/plans", headers=headers)
    assert res_plans.status_code == 200
    plans = res_plans.json()
    assert len(plans) >= 5
    codes = [p["code"] for p in plans]
    assert "starter_pos" in codes
    assert "growth_pos" in codes
    assert "pro_kds" in codes

    # 2. GET /platform/businesses/{id}/subscriptions
    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "History Cafe",
            "primary_outlet_name": "Hist Main",
            "public_slug": f"hist-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "growth_pos"}
    )

    res_history = client.get(f"/api/v1/platform/businesses/{biz_id}/subscriptions", headers=headers)
    assert res_history.status_code == 200
    history = res_history.json()
    assert len(history) == 2
    assert history[0]["is_current"] is True
    assert history[0]["status"] == "active"
    assert history[1]["is_current"] is False
    assert history[1]["status"] == "trial"


def test_plan_resolution_rejects_unknown_and_inactive(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Reject Cafe",
            "primary_outlet_name": "Reject Main",
            "public_slug": f"rej-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    # Unknown plan code -> 422 (never falls back to free_qr)
    res_unknown = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={"action_type": "change_plan", "plan_code": "completely_bogus_plan"}
    )
    assert res_unknown.status_code == 422
    assert "Unknown or inactive plan code" in res_unknown.json()["detail"]["error"]["message"]


def test_historical_start_date_requires_reason(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Historical Cafe",
            "primary_outlet_name": "Hist Main",
            "public_slug": f"hist2-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    past_start = utc_now() - timedelta(days=10)
    past_end = compute_annual_period_end(past_start)

    # No reason -> 422
    res_no_reason = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "starter_pos",
            "current_period_start": past_start.isoformat(),
            "current_period_end": past_end.isoformat(),
        }
    )
    assert res_no_reason.status_code == 422
    assert "meaningful administrative reason" in res_no_reason.json()["detail"]["error"]["message"]

    # With reason -> 200
    res_ok = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "starter_pos",
            "current_period_start": past_start.isoformat(),
            "current_period_end": past_end.isoformat(),
            "reason": "Contract signed 10 days ago per offline paper agreement"
        }
    )
    assert res_ok.status_code == 200


def test_audit_failure_transaction_rollback(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Rollback Cafe",
            "primary_outlet_name": "Rollback Main",
            "public_slug": f"roll-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Simulate audit write exception
    with patch("app.modules.businesses.platform_service.log_audit", side_effect=RuntimeError("Audit disk failure")):
        with pytest.raises(RuntimeError):
            client.patch(
                f"/api/v1/platform/businesses/{biz_id}/subscription",
                headers=headers,
                json={"action_type": "activate", "plan_code": "growth_pos"}
            )

    # Ensure transaction was rolled back and no state modified
    biz = db_session.query(Business).filter(Business.id == biz_id).first()
    assert biz.subscription_status == "trial"

    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).all()
    assert len(subs) == 1
    assert subs[0].status == "trial"


def test_fail_closed_active_sub_missing_period_end(db_session: Session):
    now = utc_now()
    biz = Business(id=uuid.uuid4(), name="Fail Closed Biz", status="active")
    db_session.add(biz)

    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=biz.id,
        plan_id=starter.id,
        status="active",
        is_current=True,
        current_period_start=now - timedelta(days=10),
        current_period_end=None,  # Missing period end!
    )
    db_session.add(sub)
    db_session.commit()

    # Must fail closed -> expired
    res = EntitlementService.check_entitlement(db_session, biz.id, "ordering.staff", now=now)
    assert res.authorized is False
    assert res.reason == "SUBSCRIPTION_EXPIRED"
    assert res.resolved_status == "expired"
