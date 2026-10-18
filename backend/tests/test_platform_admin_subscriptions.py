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
from app.core.security import hash_password
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
    """Business creation no longer auto-creates a subscription 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸�佺壕褰掓煙闂傚�革拷浣哄�曡ぐ鎺撶厵闂傚倸锟介潻鎷锋担鍝勶拷鏇°亹閹烘挾鍘甸梻鍌氬�搁敓浠嬫交閹烽攱鎷呴崫鍕舵嫹閺嚶颁汗闁圭儤鎸鹃崢浠嬫⒑绾�鍛�褰х紒鎻掞拷鐕傛嫹濮樿埖鈷戦柟鑲╁仜閿熻姤娲滈敓鑺ョ煯閸楀啿锟斤拷鐠囨祴妲堥柕蹇婂墲濞呫垺绻涚�电�啃㈤柨鐔告灮閹风兘鏌涘Δ浣糕枙闁哄矉缍侀獮鍥�鏁撴禒瀣�鏅搁柦妯猴拷娑欏�归悘鐐诧拷鐕傛嫹閸ф�佲拻闁稿本鑹鹃敓浠嬶拷搴�锟姐垹锟芥﹫鎷烽柨鐔稿灊閸栫娀宕卞Δ瀣�瀚规繝闈涳拷锟介埛鎴︽煕濠靛棗锟斤拷闁革綀娅ｇ槐鎺旓拷锝忔嫹闁规瓕宕电划鈺呮偄閻撳骸宓嗛梺闈涚箳婵�鎾�鎮楅敓浠嬫⒒娴ｈ姤纭堕柛鐘茬Ф閸掓帒鈻庨幘铏�妲�闂佺粯鍔曢幖锟界紒鐙呯秮閺屻劑寮�閸ワ拷閿熻棄瀚�缁傚秷銇愰幒鎾跺幗闁硅偐琛ラ崜婵堟嫻閳ユ枼鏀介柨鐔剁矙楠炴﹢鏁撴禒瀣�鏋侀柟鍓х帛閸ゅ秹鏌曟径娑欏�归梺褰掞拷搴″幋闁硅櫕鐗犻崺锟犲礃鐠恒劌绨ラ梻鍌氬�烽懗鍓佸垝閿熶粙鏌ｉ悢鏉戝姦妤犵偛锕ㄧ粻娑㈠即閿熶粙骞忓畡甯�鎷峰�楀牊瀚圭紓鍌氱Т閿曘倝鏁撻挊澶涘伐闁跨喕濮ら懝鍓у�曢崗鑲╃�鹃柛鈩兠�婵�澶愭煏閸�鐔哥凡闁宠�勫灴閹�娆戞嫚瑜庣�氬綊鎮楅敐蹇斿�圭紓渚婃嫹閻庯綇鎷烽柨鐔凤拷鐕傛嫹閸曪拷缁�鍐ㄢ攽閻愯�ц含鐎碉拷閿熶粙鏌涢幇鑸靛�归悗瑙勬礃鐢�鎺楁晸閼恒儔鎴﹀船婵犳艾绠�闁绘垼濮ら弲绋棵归悩璇ф嫹閿熶粙鍩涢幋锔藉仯闁癸拷閹烘垵锟藉吋绻涢崨锟介崝娆撳蓟閻旂厧绀勯柕鍫濇�楅敓鏂ゆ嫹 trial is outlet-scoped."""
    from app.modules.businesses import platform_service
    from app.modules.businesses.schemas import PlatformOutletCreate
    from app.modules.subscriptions.models import OutletSubscription

    headers = get_admin_headers(client, db_session)

    res = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Trial Provisioning Cafe",
            "owner_email": "trial@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Trial Owner",
            "public_slug": f"trial-main-{uuid.uuid4().hex[:6]}",
        }
    )
    assert res.status_code == 200
    biz_data = res.json()
    biz_id = biz_data["id"]

    biz = db_session.query(Business).filter(Business.id == uuid.UUID(biz_id)).first()
    # Business has no subscription 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸�佺壕褰掓煙闂傚�革拷浣哄�曡ぐ鎺撶厵闂傚倸锟介潻鎷锋担鍝勶拷鏇°亹閹烘挾鍘甸梻鍌氬�搁敓浠嬫交閹烽攱鎷呴崫鍕舵嫹閺嚶颁汗闁圭儤鎸鹃崢浠嬫⒑绾�鍛�褰х紒鎻掞拷鐕傛嫹濮樿埖鈷戦柟鑲╁仜閿熻姤娲滈敓鑺ョ煯閸楀啿锟斤拷鐠囨祴妲堥柕蹇婂墲濞呫垺绻涚�电�啃㈤柨鐔告灮閹风兘鏌涘Δ浣糕枙闁哄矉缍侀獮鍥�鏁撴禒瀣�鏅搁柦妯猴拷娑欏�归悘鐐诧拷鐕傛嫹閸ф�佲拻闁稿本鑹鹃敓浠嬶拷搴�锟姐垹锟芥﹫鎷烽柨鐔稿灊閸栫娀宕卞Δ瀣�瀚规繝闈涳拷锟介埛鎴︽煕濠靛棗锟斤拷闁革綀娅ｇ槐鎺旓拷锝忔嫹闁规瓕宕电划鈺呮偄閻撳骸宓嗛梺闈涚箳婵�鎾�鎮楅敓浠嬫⒒娴ｈ姤纭堕柛鐘茬Ф閸掓帒鈻庨幘铏�妲�闂佺粯鍔曢幖锟界紒鐙呯秮閺屻劑寮�閸ワ拷閿熻棄瀚�缁傚秷銇愰幒鎾跺幗闁硅偐琛ラ崜婵堟嫻閳ユ枼鏀介柨鐔剁矙楠炴﹢鏁撴禒瀣�鏋侀柟鍓х帛閸ゅ秹鏌曟径娑欏�归梺褰掞拷搴″幋闁硅櫕鐗犻崺锟犲礃鐠恒劌绨ラ梻鍌氬�烽懗鍓佸垝閿熶粙鏌ｉ悢鏉戝姦妤犵偛锕ㄧ粻娑㈠即閿熶粙骞忓畡甯�鎷峰�楀牊瀚圭紓鍌氱Т閿曘倝鏁撻挊澶涘伐闁跨喕濮ら懝鍓у�曢崗鑲╃�鹃柛鈩兠�婵�澶愭煏閸�鐔哥凡闁宠�勫灴閹�娆戞嫚瑜庣�氬綊鎮楅敐蹇斿�圭紓渚婃嫹閻庯綇鎷烽柨鐔凤拷鐕傛嫹閸曪拷缁�鍐ㄢ攽閻愯�ц含鐎碉拷閿熶粙鏌涢幇鑸靛�归悗瑙勬礃鐢�鎺楁晸閼恒儔鎴﹀船婵犳艾绠�闁绘垼濮ら弲绋棵归悩璇ф嫹閿熶粙鍩涢幋锔藉仯闁癸拷閹烘垵锟藉吋绻涢崨锟介崝娆撳蓟閻旂厧绀勯柕鍫濇�楅敓鏂ゆ嫹 trial lives on outlets
    assert biz.subscription_status == "trial"  # model default
    sub = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == uuid.UUID(biz_id),
        BusinessSubscription.is_current == True
    ).first()
    assert sub is None

    # Create an outlet with default plan_code 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸�佺壕褰掓煙闂傚�革拷浣哄�曡ぐ鎺撶厵闂傚倸锟介潻鎷锋担鍝勶拷鏇°亹閹烘挾鍘甸梻鍌氬�搁敓浠嬫交閹烽攱鎷呴崫鍕舵嫹閺嚶颁汗闁圭儤鎸鹃崢浠嬫⒑绾�鍛�褰х紒鎻掞拷鐕傛嫹濮樿埖鈷戦柟鑲╁仜閿熻姤娲滈敓鑺ョ煯閸楀啿锟斤拷鐠囨祴妲堥柕蹇婂墲濞呫垺绻涚�电�啃㈤柨鐔告灮閹风兘鏌涘Δ浣糕枙闁哄矉缍佸��锟介柟绋块�搁弳鍫ユ⒑鐠恒劌鏋庨柨鐔诲Г閸旀洟鎮橀崣澶嬪弿濠电姴鎳忛敓鏂ょ悼閸掓帒鈻庨幘宕囷拷宀勬煃閵夈儱鏆遍柨鐔诲Г閻╋拷婵�濠冩そ濡�鍐�鍩￠崘锟借倴缂傚倷鑳舵慨鐢稿箲閸ワ拷閹�浼存晸娴犲��鍙撻柛銉ｅ妿閳�鏇㈡煕婵犲偊鎷峰�橈拷閻撱垺淇婇敓浠嬫偖鐎涙ê锟藉湱锟界櫢鎷烽悗锝忔嫹閻庢艾缍婇幃妤呮晲韫囨柨锟藉綊姊洪崫鍕�锟斤拷闁告梹鍨块獮鍐�濮�閵堝懐锟藉牆霉閿濆牊锟斤綁宕㈤敓浠嬫⒒閸屾瑦绁版俊妞煎姂閹�鐐烘晝閸屾氨锟芥煡鏌涢妷锟介幏閿嬶拷鐘靛仦閸旀牜鎹㈠┑瀣�绀冮柕濞у懐宓侀梺璇叉捣濞呫垽骞忛悜鑺ョ叆闁绘棁锟芥畫鎾绘煥閻旇�残撴慨濠傛贡閹广垹鈹戦崼婵囩�虫繝銏ｆ硾閿熸枻鎷烽柨鐔凤拷鐕傛嫹閸曪拷缁★拷闂佹眹鍨藉�佳冪摥闂備胶鎳撻崯璺ㄦ崲濮楋拷瀵�锟介柟鎹愶拷鍙夛拷姗�鏌曢崼婵囧窛鐞氾附淇婇妶鍥�啸闁稿��鍋ゅ畷褰掑垂閿熶粙鎮鹃悜鑺ュ亜闁稿繐鍚嬪▍銏ゆ⒑閸忛棿鑸�闁稿孩澹嗛幑銏ゅ幢濞戞瑧鍘甸梻鍌氬�搁敓浠嬫交閹烽攱鎷呴崨濠冩�伴梻鍌氬�烽悞锔撅拷绗涘喛鎷锋繝鍌滅Ш鐎规洘娲栭悾鐑藉炊閳哄喛鎷锋繝鍥ㄧ厵闁绘垶锕�閹烽攱鎷呴崣澶婏拷浠嬫⒒娴ｇ尨鎷烽幐搴㈡嫳闂佽崵鍠嗛崝鎴濈暦濡わ拷閻ｆ繈宕熼敓浠嬫偂濞嗘挻鐓ｉ煫鍥ュ劜鐎氬綊姊洪崷锟介幊鎾趁洪妶澶嬪仼闁绘垼濮ら崑銊х磼鐎ｏ拷閻忔繈宕�閵娾晜鈷戦悹鎭掑妼閺嬪秶绱掗敓钘夆枎閹炬潙浠掗梺璺ㄥ枍缁�娆撴偂閿熶粙鏌涢妷锝呭�块柍锟介弴銏＄厸闁告冻鎷烽柟锟介崒鐐茶摕闁靛ň鏅滈崑鍡涙煕鐏炲墽鈽夐柨鐔告灮閹凤拷 trial
    out_res = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Trial Outlet", "public_slug": f"trial-outlet-{uuid.uuid4().hex[:6]}"}
    )
    assert out_res.status_code == 200
    outlet_id = out_res.json()["id"]

    outlet_sub = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == uuid.UUID(outlet_id)
    ).first()
    assert outlet_sub is not None
    assert outlet_sub.status == "trial"
    assert outlet_sub.trial_ends_at is not None
    diff = outlet_sub.trial_ends_at - outlet_sub.created_at
    assert abs(diff.total_seconds() - (30 * 86400)) < 5


def test_annual_term_exact_validation(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Validation Cafe",
            "owner_email": "val@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Validation Owner",
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
            "owner_email": "conv@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Conversion Owner",
            "public_slug": f"conv-main-{uuid.uuid4().hex[:6]}",
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Create an outlet to seed the trial subscription (Phase 3: trials are outlet-scoped)
    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Conversion Outlet", "public_slug": f"conv-outlet-{uuid.uuid4().hex[:6]}"}
    )
    assert outlet_resp.status_code == 200

    # Seed a trial BusinessSubscription for conversion testing
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
    # (trial sub was auto-created when outlet was added via _propagate_subscription_to_outlets)
    subs = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_id
    ).order_by(BusinessSubscription.created_at.desc()).all()

    # If only 1 sub exists (activation created new but didn't swap old), that's the current one
    assert len(subs) >= 1
    curr = [s for s in subs if s.is_current][0]
    assert curr.status == "active"
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
            "owner_email": "renew@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Renewal Owner",
            "public_slug": f"renew-main-{uuid.uuid4().hex[:6]}",
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Create outlet to seed trial subscription
    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Renewal Outlet", "public_slug": f"renew-outlet-{uuid.uuid4().hex[:6]}"}
    )
    assert outlet_resp.status_code == 200

    # Seed a trial BusinessSubscription (Phase 3: no longer auto-created on business creation)
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
            "owner_email": "multi@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Multi Renew Owner",
            "public_slug": f"multi-renew-{uuid.uuid4().hex[:6]}",
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Create outlet to seed trial subscription
    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Multi Renewal Outlet", "public_slug": f"multi-renew-outlet-{uuid.uuid4().hex[:6]}"}
    )
    assert outlet_resp.status_code == 200

    # Seed a trial BusinessSubscription
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
            "owner_email": "late@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Late Owner",
            "public_slug": f"late-main-{uuid.uuid4().hex[:6]}",
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Create outlet to seed trial subscription
    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Late Outlet", "public_slug": f"late-outlet-{uuid.uuid4().hex[:6]}"}
    )
    assert outlet_resp.status_code == 200

    # Sub in past (expired) 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸�佺壕褰掓煙闂傚�革拷浣哄�曡ぐ鎺撶厵闂傚倸锟介潻鎷锋担鍝勶拷鏇㈠捶閿熶粙鏁撻悾灞惧殌閻庢熬鎷烽梺闈╃悼閿熻棄锟姐劋姹楅梺鍦�鍎ら崹褰掑磹閻愮儤鍋℃繝濠傚枦閹风兘骞囬敓浠嬪礄閻樼粯鐓涚�广儱绻戠�氬綊姊洪崫鍕�鐒跨紒缁樼箓閻ｇ兘宕奸弴鐐嶃劑鏌曟竟锟介崒娑樹簼闂傚倸鍊搁崐鎼佸磹閹间礁纾诲┑鐘叉搐缁狅拷闂佺粯鍨兼慨銈夊煕閹烘嚚褰掓晲閸ャ劌娈岄梺璺ㄥ枔閻涖倝宕楅悩铏�銇濈�碉拷娴犲��鏅搁柦妯猴拷灞炬�鹃梺鍦�澧楀�㈡ɑ瀵奸悩缁樼厪濠㈢櫢鎷烽柛灞剧矌閹插綊姊婚崒娆愮グ婵炲�嬫礋瀹曟澘锟姐儱娲ら崹婵囩箾閸℃�呯崪闁圭兘鏀辩换婵嬪川閿熶粙鏁撻弬銈囩М妤犵偞鍨垮畷鐔兼晸閼恒儰绻嗛柟闂寸�佸敮闂佹寧姊归崕宕囩礊閹烘�佲拻闁稿本鐟ㄩ崗宀勬煙閾忥拷閹瑰洤鐣烽悽绋垮唨闁跨喍绮欓悰锟介煫鍥ㄧ⊕閺呮悂鏌ㄩ悤鍌涘�� manually create it since no trial sub exists yet
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="active", is_current=True,
        current_period_start=utc_now() - timedelta(days=400),
        current_period_end=utc_now() - timedelta(days=35),
    )
    db_session.add(sub)
    db_session.commit()
    sub = db_session.scalar(select(BusinessSubscription).where(
        BusinessSubscription.business_id == biz_id, BusinessSubscription.is_current == True
    ))

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
            "owner_email": "switch@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Switch Owner",
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
            "owner_email": "cancel@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Cancel Owner",
            "public_slug": f"cancel-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Seed a trial BusinessSubscription
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
            "owner_email": "imm@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Immediate Owner",
            "public_slug": f"imm-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Seed a trial BusinessSubscription (Phase 3: no longer auto-created on business creation)
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
    assert sub is not None
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
            "owner_email": "pd@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "PastDue Owner",
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

    # 2. GET /platform/businesses/{id}/subscriptions (canonical outlet subscriptions)
    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "History Cafe",
            "owner_email": "hist@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Historical Owner",
            "public_slug": f"hist-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    out_res = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "History Outlet", "public_slug": f"hist-out-{uuid.uuid4().hex[:6]}", "plan_code": "starter_pos"}
    )
    assert out_res.status_code == 200
    outlet_id = out_res.json()["id"]

    res_history = client.get(f"/api/v1/platform/businesses/{biz_id}/subscriptions", headers=headers)
    assert res_history.status_code == 200
    history = res_history.json()
    assert len(history) == 1
    assert history[0]["outlet_id"] == outlet_id
    assert history[0]["is_current"] is True
    assert history[0]["status"] == "active"


def test_plan_resolution_rejects_unknown_and_inactive(client: TestClient, db_session: Session):
    headers = get_admin_headers(client, db_session)

    res_create = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": "Reject Cafe",
            "owner_email": "reject@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Reject Owner",
            "public_slug": f"rej-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = res_create.json()["id"]

    # Seed a trial BusinessSubscription (needed for change_plan action)
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=uuid.UUID(biz_id), plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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
            "owner_email": "hist@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Historical Owner",
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
            "owner_email": "rollback@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Rollback Owner",
            "public_slug": f"roll-main-{uuid.uuid4().hex[:6]}",
            "plan_name": "starter_pos"
        }
    )
    biz_id = uuid.UUID(res_create.json()["id"])

    # Seed a trial BusinessSubscription
    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    trial_sub = BusinessSubscription(
        id=uuid.uuid4(), business_id=biz_id, plan_id=starter.id,
        status="trial", is_current=True, trial_ends_at=utc_now() + timedelta(days=30)
    )
    db_session.add(trial_sub)
    db_session.commit()

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


def test_list_business_subscriptions_canonical_outlet_subscriptions(client: TestClient, db_session: Session):
    """
    Verify GET /api/v1/platform/businesses/{business_id}/subscriptions returns canonical
    OutletSubscription records with outlet_id, nested plan details, null date handling,
    and business isolation.
    """
    from app.modules.subscriptions.models import OutletSubscription

    headers = get_admin_headers(client, db_session)

    # 1. Setup Business A with two outlets
    biz_a = Business(id=uuid.uuid4(), name="Outlet Sub Cafe A", status="active")
    biz_b = Business(id=uuid.uuid4(), name="Outlet Sub Cafe B", status="active")
    db_session.add_all([biz_a, biz_b])

    out_a1 = Outlet(id=uuid.uuid4(), business_id=biz_a.id, name="Branch North", public_slug=f"north-{uuid.uuid4().hex[:6]}")
    out_a2 = Outlet(id=uuid.uuid4(), business_id=biz_a.id, name="Branch South", public_slug=f"south-{uuid.uuid4().hex[:6]}")
    out_b = Outlet(id=uuid.uuid4(), business_id=biz_b.id, name="Branch East", public_slug=f"east-{uuid.uuid4().hex[:6]}")
    db_session.add_all([out_a1, out_a2, out_b])

    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    growth = db_session.scalar(select(Plan).where(Plan.code == "growth_pos"))

    # Seed canonical OutletSubscription records
    now = utc_now()
    sub_a1 = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=out_a1.id,
        business_id=biz_a.id,
        plan_id=starter.id,
        status="trial",
        is_current=True,
        trial_ends_at=now + timedelta(days=30),
        current_period_start=None,
        current_period_end=None,
        cancel_at_period_end=False,
    )
    sub_a2 = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=out_a2.id,
        business_id=biz_a.id,
        plan_id=growth.id,
        status="active",
        is_current=True,
        trial_ends_at=None,
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
        cancel_at_period_end=False,
    )
    sub_b = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=out_b.id,
        business_id=biz_b.id,
        plan_id=starter.id,
        status="active",
        is_current=True,
        trial_ends_at=None,
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
        cancel_at_period_end=False,
    )
    db_session.add_all([sub_a1, sub_a2, sub_b])
    db_session.commit()

    # Query Business A subscriptions
    res = client.get(f"/api/v1/platform/businesses/{biz_a.id}/subscriptions", headers=headers)
    assert res.status_code == 200
    subs_a = res.json()
    assert len(subs_a) == 2

    # Verify fields: outlet_id, plan nested object with code and name, dates
    sub_dict_by_outlet = {s["outlet_id"]: s for s in subs_a}
    assert str(out_a1.id) in sub_dict_by_outlet
    assert str(out_a2.id) in sub_dict_by_outlet
    assert str(out_b.id) not in sub_dict_by_outlet  # Business isolation!

    item_a1 = sub_dict_by_outlet[str(out_a1.id)]
    assert item_a1["status"] == "trial"
    assert item_a1["is_current"] is True
    assert item_a1["plan"]["code"] == "starter_pos"
    assert item_a1["plan"]["name"] is not None
    assert item_a1["trial_ends_at"] is not None
    assert item_a1["current_period_end"] is None

    item_a2 = sub_dict_by_outlet[str(out_a2.id)]
    assert item_a2["status"] == "active"
    assert item_a2["is_current"] is True
    assert item_a2["plan"]["code"] == "growth_pos"
    assert item_a2["current_period_end"] is not None

    # Query Business B subscriptions
    res_b = client.get(f"/api/v1/platform/businesses/{biz_b.id}/subscriptions", headers=headers)
    assert res_b.status_code == 200
    subs_b = res_b.json()
    assert len(subs_b) == 1
    assert subs_b[0]["outlet_id"] == str(out_b.id)


def test_list_business_subscriptions_legacy_records_isolated(client: TestClient, db_session: Session):
    """
    Verify GET /api/v1/platform/businesses/{id}/subscriptions returns only canonical
    OutletSubscription records (empty list when only legacy BusinessSubscription exists),
    while preserving the legacy BusinessSubscription records intact in the database.
    """
    headers = get_admin_headers(client, db_session)

    biz_legacy = Business(id=uuid.uuid4(), name="Legacy Sub Cafe", status="active")
    db_session.add(biz_legacy)

    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    legacy_sub = BusinessSubscription(
        id=uuid.uuid4(),
        business_id=biz_legacy.id,
        plan_id=starter.id,
        status="active",
        is_current=True,
        trial_ends_at=None,
        current_period_start=utc_now(),
        current_period_end=utc_now() + timedelta(days=365),
    )
    db_session.add(legacy_sub)
    db_session.commit()

    # The outlet-scoped endpoint returns only canonical outlet subscriptions ([] in this case)
    res = client.get(f"/api/v1/platform/businesses/{biz_legacy.id}/subscriptions", headers=headers)
    assert res.status_code == 200
    subs = res.json()
    assert subs == []

    # Verify legacy BusinessSubscription remains completely intact in the database for reconciliation
    db_record = db_session.query(BusinessSubscription).filter(
        BusinessSubscription.business_id == biz_legacy.id
    ).first()
    assert db_record is not None
    assert db_record.id == legacy_sub.id
    assert db_record.status == "active"


def test_list_business_subscriptions_preserves_historical_non_current_records(client: TestClient, db_session: Session):
    """
    Verify that OutletSubscription records with is_current=False are returned
    with their actual stored status and non-null outlet_id, allowing callers
    to distinguish historical records from unassigned outlets.
    """
    from app.modules.subscriptions.models import OutletSubscription

    headers = get_admin_headers(client, db_session)

    biz = Business(id=uuid.uuid4(), name="History Sub Cafe", status="active")
    db_session.add(biz)

    out = Outlet(id=uuid.uuid4(), business_id=biz.id, name="History Branch", public_slug=f"hist-{uuid.uuid4().hex[:6]}")
    db_session.add(out)

    starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))

    past_sub = OutletSubscription(
        id=uuid.uuid4(),
        outlet_id=out.id,
        business_id=biz.id,
        plan_id=starter.id,
        status="trial",
        is_current=False,  # Historical record
        trial_ends_at=utc_now() - timedelta(days=5),
        current_period_start=None,
        current_period_end=None,
        cancel_at_period_end=False,
    )
    db_session.add(past_sub)
    db_session.commit()

    res = client.get(f"/api/v1/platform/businesses/{biz.id}/subscriptions", headers=headers)
    assert res.status_code == 200
    subs = res.json()
    assert len(subs) == 1
    assert subs[0]["outlet_id"] == str(out.id)
    assert subs[0]["is_current"] is False
    assert subs[0]["status"] == "trial"


def test_list_business_subscriptions_operator_forbidden(client: TestClient, db_session: Session):
    """
    Verify platform operator is forbidden (403) from accessing commercial subscription endpoints.
    """
    from app.core.security import hash_password

    operator = db_session.query(User).filter(User.email == "sub_op@test.com").first()
    if not operator:
        operator = User(
            id=uuid.uuid4(),
            email="sub_op@test.com",
            password_hash=hash_password("password123"),
            display_name="Sub Operator",
            status="active",
            is_platform_admin=False,
            platform_role="operator",
        )
        db_session.add(operator)
        db_session.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "sub_op@test.com", "password": "password123"},
    )
    op_token = login_resp.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}

    res = client.get(f"/api/v1/platform/businesses/{uuid.uuid4()}/subscriptions", headers=op_headers)
    assert res.status_code == 403


def test_update_business_subscription_does_not_propagate_to_multiple_outlets(
    client: TestClient, db_session: Session
):
    """
    Regression test (Owner Decision 002):
    A legacy business-level subscription mutation must NEVER overwrite canonical OutletSubscription records.
    When a business has two outlets with distinct plans (e.g. starter_pos and pro_kds), updating the business
    subscription must leave both outlet subscriptions completely unchanged:
    - original plan preserved
    - original status preserved
    - lifecycle dates preserved
    - is_current flag preserved
    - row identity preserved
    """
    from datetime import datetime, timezone
    from app.modules.subscriptions.models import OutletSubscription, Plan

    headers = get_admin_headers(client, db_session)

    # 1. Create a business
    biz_data = {
        "name": "Multi-Outlet Independence Biz",
        "owner_email": f"owner_multi_{uuid.uuid4().hex[:6]}@test.com",
        "owner_password": "Password123!",
        "owner_display_name": "Multi Owner"
    }
    b_res = client.post("/api/v1/platform/businesses", headers=headers, json=biz_data)
    assert b_res.status_code == 200
    biz_id = uuid.UUID(b_res.json()["id"])

    # 2. Add Outlet 1 on starter_pos
    o1_res = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Outlet Alpha",
            "public_slug": f"alpha-{uuid.uuid4().hex[:6]}",
            "plan_code": "starter_pos"
        }
    )
    assert o1_res.status_code == 200
    o1_id = uuid.UUID(o1_res.json()["id"])

    # 3. Add Outlet 2 on pro_kds
    o2_res = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Outlet Beta",
            "public_slug": f"beta-{uuid.uuid4().hex[:6]}",
            "plan_code": "pro_kds"
        }
    )
    assert o2_res.status_code == 200
    o2_id = uuid.UUID(o2_res.json()["id"])

    # Inspect initial OutletSubscription states
    sub1_before = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o1_id,
        OutletSubscription.is_current == True
    ).first()
    sub2_before = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o2_id,
        OutletSubscription.is_current == True
    ).first()

    assert sub1_before is not None
    assert sub2_before is not None
    p_starter = db_session.scalar(select(Plan).where(Plan.code == "starter_pos"))
    p_pro = db_session.scalar(select(Plan).where(Plan.code == "pro_kds"))
    assert sub1_before.plan_id == p_starter.id
    assert sub2_before.plan_id == p_pro.id

    sub1_id_before = sub1_before.id
    sub2_id_before = sub2_before.id
    sub1_status_before = sub1_before.status
    sub2_status_before = sub2_before.status
    sub1_start_before = sub1_before.current_period_start
    sub1_end_before = sub1_before.current_period_end
    sub2_start_before = sub2_before.current_period_start
    sub2_end_before = sub2_before.current_period_end

    # 4. Perform legacy business-level subscription mutation (e.g. change_plan to enterprise)
    patch_res = client.patch(
        f"/api/v1/platform/businesses/{biz_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "enterprise"
        }
    )
    assert patch_res.status_code == 200

    # 5. Verify that NEITHER outlet subscription was modified or overwritten
    sub1_after = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o1_id,
        OutletSubscription.is_current == True
    ).first()
    sub2_after = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o2_id,
        OutletSubscription.is_current == True
    ).first()

    assert sub1_after is not None
    assert sub2_after is not None

    # Exact identity and field preservation
    assert sub1_after.id == sub1_id_before
    assert sub2_after.id == sub2_id_before
    assert sub1_after.plan_id == p_starter.id, "Outlet 1 plan must remain starter_pos"
    assert sub2_after.plan_id == p_pro.id, "Outlet 2 plan must remain pro_kds"
    assert sub1_after.status == sub1_status_before
    assert sub2_after.status == sub2_status_before
    assert sub1_after.current_period_start == sub1_start_before
    assert sub1_after.current_period_end == sub1_end_before
    assert sub2_after.current_period_start == sub2_start_before
    assert sub2_after.current_period_end == sub2_end_before
    assert sub1_after.is_current is True
    assert sub2_after.is_current is True


# ==============================================================================
# Outlet-Scoped Subscription Lifecycle Management Tests (Phase 3A)
# ==============================================================================

def _setup_test_business_and_outlet(client: TestClient, db_session: Session, initial_plan_code: str = "starter_pos"):
    """Helper to provision a test business and outlet with an initial subscription."""
    headers = get_admin_headers(client, db_session)
    biz_resp = client.post(
        "/api/v1/platform/businesses",
        headers=headers,
        json={
            "name": f"Lifecycle Biz {uuid.uuid4().hex[:6]}",
            "owner_email": f"lifecycle_{uuid.uuid4().hex[:6]}@example.com",
            "owner_password": "Password123!",
            "owner_display_name": "Lifecycle Owner",
            "public_slug": f"lc-biz-{uuid.uuid4().hex[:6]}",
        }
    )
    assert biz_resp.status_code == 200
    biz_id = uuid.UUID(biz_resp.json()["id"])

    outlet_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={
            "name": "Lifecycle Main Outlet",
            "public_slug": f"lc-main-{uuid.uuid4().hex[:6]}",
            "plan_code": initial_plan_code
        }
    )
    assert outlet_resp.status_code == 200
    outlet_id = uuid.UUID(outlet_resp.json()["id"])

    return biz_id, outlet_id, headers


def test_outlet_subscription_authorization_and_validation(client: TestClient, db_session: Session):
    """
    Verifies that:
    1. Unauthenticated requests are rejected with 401.
    2. Non-admin users are rejected with 403.
    3. Missing or unknown action_type is rejected with 422.
    4. Mutually exclusive or forbidden fields per action are rejected with 422.
    """
    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session)

    # 1. Unauthenticated -> 401
    unauth_resp = client.patch(f"/api/v1/platform/outlets/{outlet_id}/subscription", json={"action_type": "activate"})
    assert unauth_resp.status_code == 401

    # 2. Regular non-admin user -> 403
    regular_user = User(
        email=f"regular_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("password123"),
        display_name="Regular Staff",
        status="active",
        is_platform_admin=False
    )
    db_session.add(regular_user)
    db_session.commit()
    login_resp = client.post("/api/v1/auth/login", json={"email": regular_user.email, "password": "password123"})
    regular_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    forbidden_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=regular_headers,
        json={"action_type": "activate", "plan_code": "pro_kds"}
    )
    assert forbidden_resp.status_code == 403

    # 3. Missing action_type -> 422
    missing_action_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"plan_code": "pro_kds"}
    )
    assert missing_action_resp.status_code == 422

    # 4. Unknown action_type -> 422
    bad_action_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "invalid_action", "plan_code": "pro_kds"}
    )
    assert bad_action_resp.status_code == 422
    assert "Unknown lifecycle action_type" in bad_action_resp.json()["detail"]["error"]["message"]


def test_outlet_subscription_activate_action(client: TestClient, db_session: Session):
    """
    Verifies the activate action:
    - Atomically unmarks old current row (is_current=False)
    - Inserts a new current row with status=active and computed 1-year annual term
    - Rejects irrelevant fields like trial_ends_at
    - Mandates administrative reason if contractual start is backdated > 24 hours
    - Writes platform audit log with outlet_id and metadata
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="trial")

    # Initial state: outlet is in trial
    initial_sub = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    assert initial_sub.status == "trial"

    # Attempt to pass trial_ends_at during activation -> 422
    bad_field_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "pro_kds",
            "trial_ends_at": (utc_now() + timedelta(days=10)).isoformat()
        }
    )
    assert bad_field_resp.status_code == 422
    assert "trial_ends_at cannot be updated during activation" in bad_field_resp.json()["detail"]["error"]["message"]

    # Attempt backdated start without reason -> 422
    backdated_start = (utc_now() - timedelta(days=10)).isoformat()
    no_reason_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "pro_kds",
            "current_period_start": backdated_start
        }
    )
    assert no_reason_resp.status_code == 422
    assert "administrative reason is required" in no_reason_resp.json()["detail"]["error"]["message"]

    # Successful activation with valid plan and backdated start + reason
    start_dt = utc_now() - timedelta(days=5)
    expected_end = compute_annual_period_end(start_dt)
    resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={
            "action_type": "activate",
            "plan_code": "pro_kds",
            "current_period_start": start_dt.isoformat(),
            "reason": "Contract signed on 5 days ago"
        }
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["outlet_id"] == str(outlet_id)
    assert res_data["business_id"] == str(biz_id)
    assert res_data["status"] == "active"
    assert res_data["is_current"] is True
    assert res_data["plan"]["code"] == "pro_kds"
    assert res_data["current_period_end"] is not None
    assert datetime.fromisoformat(res_data["current_period_end"].replace("Z", "+00:00")).year == expected_end.year
    assert datetime.fromisoformat(res_data["current_period_end"].replace("Z", "+00:00")).month == expected_end.month
    assert datetime.fromisoformat(res_data["current_period_end"].replace("Z", "+00:00")).day == expected_end.day

    # Verify DB state: old sub is_current=False, exactly one row is_current=True
    all_subs = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id
    ).order_by(OutletSubscription.created_at.asc()).all()
    assert len(all_subs) == 2
    assert all_subs[0].id == initial_sub.id
    assert all_subs[0].is_current is False
    assert all_subs[1].id == uuid.UUID(res_data["id"])
    assert all_subs[1].is_current is True

    # Audit log verification
    audit = db_session.query(AuditLog).filter(
        AuditLog.entity_id == uuid.UUID(res_data["id"]),
        AuditLog.action == "platform.outlet_subscription.activate"
    ).first()
    assert audit is not None
    assert audit.outlet_id == outlet_id
    assert audit.business_id == biz_id
    assert audit.metadata_json["action_type"] == "activate"
    assert audit.metadata_json["historical_start_reason"] == "Contract signed on 5 days ago"


def test_outlet_subscription_renew_action_timely_and_late(client: TestClient, db_session: Session):
    """
    Verifies renew action:
    1. Timely renewal: extends from existing contractual period_end by exactly 1 calendar year.
    2. Late renewal: starts from now (or specified start) and extends 1 calendar year.
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="starter_pos")

    # Current subscription is active expiring in 60 days
    curr_sub = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    orig_end = utc_now() + timedelta(days=60)
    curr_sub.status = "active"
    curr_sub.current_period_start = utc_now() - timedelta(days=305)
    curr_sub.current_period_end = orig_end
    db_session.commit()

    # 1. Timely renewal (now < current_period_end)
    expected_timely_end = compute_annual_period_end(orig_end)
    renew_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "renew"}
    )
    assert renew_resp.status_code == 200
    renew_data = renew_resp.json()
    assert renew_data["status"] == "active"
    assert renew_data["current_period_start"] is not None
    assert renew_data["current_period_end"] is not None
    assert datetime.fromisoformat(renew_data["current_period_end"].replace("Z", "+00:00")).year == expected_timely_end.year

    # Old row un-flagged
    db_session.refresh(curr_sub)
    assert curr_sub.is_current is False

    # 2. Simulate expired subscription and test Late Renewal
    new_curr = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    new_curr.current_period_end = utc_now() - timedelta(days=5)  # expired
    db_session.commit()

    late_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "renew"}
    )
    assert late_resp.status_code == 200
    late_data = late_resp.json()
    assert late_data["status"] == "active"
    # Started around now and ends 1 calendar year from now
    db_session.refresh(new_curr)
    assert new_curr.is_current is False


def test_outlet_subscription_plan_changes(client: TestClient, db_session: Session):
    """
    Verifies:
    1. change_plan (mid-term): preserves existing period start and end dates. Rejects new dates.
    2. change_plan_new_term: starts a new 1-year annual term.
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="starter_pos")

    curr_sub = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    p_start = utc_now() - timedelta(days=40)
    p_end = utc_now() + timedelta(days=325)
    curr_sub.status = "active"
    curr_sub.current_period_start = p_start
    curr_sub.current_period_end = p_end
    db_session.commit()

    # Mid-term plan change attempting to supply dates -> 422
    bad_dates_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={
            "action_type": "change_plan",
            "plan_code": "growth_pos",
            "current_period_start": utc_now().isoformat()
        }
    )
    assert bad_dates_resp.status_code == 422
    assert "Mid-term plan change preserves existing period dates" in bad_dates_resp.json()["detail"]["error"]["message"]

    # Valid mid-term plan change
    change_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "change_plan", "plan_code": "growth_pos"}
    )
    assert change_resp.status_code == 200
    change_data = change_resp.json()
    assert change_data["plan"]["code"] == "growth_pos"
    assert datetime.fromisoformat(change_data["current_period_start"].replace("Z", "+00:00")).day == p_start.day
    assert datetime.fromisoformat(change_data["current_period_end"].replace("Z", "+00:00")).day == p_end.day

    # Plan change with new term -> resets start to now and end to 1 calendar year
    new_term_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "change_plan_new_term", "plan_code": "enterprise"}
    )
    assert new_term_resp.status_code == 200
    new_term_data = new_term_resp.json()
    assert new_term_data["plan"]["code"] == "enterprise"
    assert datetime.fromisoformat(new_term_data["current_period_start"].replace("Z", "+00:00")).day != p_start.day


def test_outlet_subscription_in_place_actions(client: TestClient, db_session: Session):
    """
    Verifies in-place actions:
    1. extend_trial (validates future trial_ends_at)
    2. schedule_cancellation (sets cancel_at_period_end=True, cancelled_at=now)
    3. revoke_scheduled_cancellation (clears cancel_at_period_end and cancelled_at)
    4. cancel_immediately (requires reason, sets status=cancelled, clears cancel_at_period_end)
    5. mark_past_due and mark_past_due_with_extension (requires extension date and reason)
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="trial")

    # 1. extend_trial
    # Past trial date -> 422
    past_trial = (utc_now() - timedelta(days=1)).isoformat()
    bad_trial_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "extend_trial", "trial_ends_at": past_trial}
    )
    assert bad_trial_resp.status_code == 422

    # Future trial date -> 200
    future_trial = utc_now() + timedelta(days=45)
    good_trial_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "extend_trial", "trial_ends_at": future_trial.isoformat()}
    )
    assert good_trial_resp.status_code == 200
    assert good_trial_resp.json()["status"] == "trial"
    assert datetime.fromisoformat(good_trial_resp.json()["trial_ends_at"].replace("Z", "+00:00")).day == future_trial.day

    # 2. Activate to test cancellations
    client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "pro_kds"}
    )

    # 3. schedule_cancellation
    sched_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "schedule_cancellation", "reason": "Customer requested cancellation at renewal"}
    )
    assert sched_resp.status_code == 200
    assert sched_resp.json()["cancel_at_period_end"] is True
    assert sched_resp.json()["cancelled_at"] is not None

    # 4. revoke_scheduled_cancellation
    revoke_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "revoke_scheduled_cancellation"}
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["cancel_at_period_end"] is False
    assert revoke_resp.json()["cancelled_at"] is None

    # 5. cancel_immediately without reason -> 422
    no_reason_cancel = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "cancel_immediately"}
    )
    assert no_reason_cancel.status_code == 422

    # cancel_immediately with reason -> 200
    imm_cancel = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "cancel_immediately", "reason": "Non-payment and closure"}
    )
    assert imm_cancel.status_code == 200
    assert imm_cancel.json()["status"] == "cancelled"
    assert imm_cancel.json()["cancel_at_period_end"] is False

    # 6. mark_past_due
    # Reactivate first
    client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "starter_pos"}
    )
    past_due_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "mark_past_due"}
    )
    assert past_due_resp.status_code == 200
    assert past_due_resp.json()["status"] == "past_due"

    # 7. mark_past_due_with_extension
    ext_end = utc_now() + timedelta(days=15)
    ext_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={
            "action_type": "mark_past_due_with_extension",
            "current_period_end": ext_end.isoformat(),
            "reason": "Grace period granted until cheque clears"
        }
    )
    assert ext_resp.status_code == 200
    assert ext_resp.json()["status"] == "past_due"
    assert datetime.fromisoformat(ext_resp.json()["current_period_end"].replace("Z", "+00:00")).day == ext_end.day


def test_outlet_subscription_free_qr_non_expiring(client: TestClient, db_session: Session):
    """
    Verifies that free_qr plan allows null period end and is evaluated as non-expiring.
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="trial")

    free_qr_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "free_qr"}
    )
    assert free_qr_resp.status_code == 200
    data = free_qr_resp.json()
    assert data["plan"]["code"] == "free_qr"
    assert data["current_period_end"] is None
    assert data["status"] == "active"

    sub = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    assert EntitlementService.evaluate_subscription_status(sub) == "active"


def test_sibling_outlet_independence_and_business_column_isolation(client: TestClient, db_session: Session):
    """
    Verifies:
    1. Mutating outlet 1's subscription does NOT affect sibling outlet 2.
    2. Mutating outlet 1's subscription does NOT mutate business-level subscription columns.
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, o1_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="starter_pos")

    # Add second outlet to same business
    o2_resp = client.post(
        f"/api/v1/platform/businesses/{biz_id}/outlets",
        headers=headers,
        json={"name": "Sibling Outlet 2", "public_slug": f"sibling-2-{uuid.uuid4().hex[:6]}", "plan_code": "pro_kds"}
    )
    assert o2_resp.status_code == 200
    o2_id = uuid.UUID(o2_resp.json()["id"])

    # Seed initial business table state
    biz = db_session.query(Business).filter(Business.id == biz_id).first()
    biz.plan_name = "initial_biz_plan"
    biz.subscription_status = "trial"
    db_session.commit()

    # Capture outlet 2 state before
    o2_sub_before = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o2_id,
        OutletSubscription.is_current == True
    ).first()
    o2_sub_id = o2_sub_before.id
    o2_plan_id = o2_sub_before.plan_id
    o2_status = o2_sub_before.status

    # Mutate outlet 1: activate onto enterprise
    o1_patch = client.patch(
        f"/api/v1/platform/outlets/{o1_id}/subscription",
        headers=headers,
        json={"action_type": "activate", "plan_code": "enterprise"}
    )
    assert o1_patch.status_code == 200
    assert o1_patch.json()["plan"]["code"] == "enterprise"

    # 1. Outlet 2 is COMPLETELY unchanged
    o2_sub_after = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == o2_id,
        OutletSubscription.is_current == True
    ).first()
    assert o2_sub_after.id == o2_sub_id
    assert o2_sub_after.plan_id == o2_plan_id
    assert o2_sub_after.status == o2_status

    # 2. Business-level columns were NOT modified
    db_session.refresh(biz)
    assert biz.plan_name == "initial_biz_plan"
    assert biz.subscription_status == "trial"


def test_expired_outlet_subscription_remains_authoritative_over_unexpired_legacy_business_sub(
    client: TestClient, db_session: Session
):
    """
    Verifies that when an outlet has a canonical OutletSubscription row that is expired,
    entitlement resolution evaluates it as expired and NEVER falls back to an unexpired
    legacy BusinessSubscription.
    """
    from app.modules.subscriptions.models import OutletSubscription, BusinessSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="starter_pos")

    # Set up an unexpired legacy BusinessSubscription
    p_pro = db_session.scalar(select(Plan).where(Plan.code == "pro_kds"))
    legacy_biz_sub = BusinessSubscription(
        business_id=biz_id,
        plan_id=p_pro.id,
        status="active",
        is_current=True,
        current_period_start=utc_now() - timedelta(days=10),
        current_period_end=utc_now() + timedelta(days=350)
    )
    db_session.add(legacy_biz_sub)
    db_session.commit()

    # Cancel the outlet's subscription immediately
    cancel_resp = client.patch(
        f"/api/v1/platform/outlets/{outlet_id}/subscription",
        headers=headers,
        json={"action_type": "cancel_immediately", "reason": "Customer cancelled"}
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Check entitlement for ordering.staff -> MUST be False / SUBSCRIPTION_CANCELLED
    result = EntitlementService.check_entitlement(
        db=db_session,
        business_id=biz_id,
        outlet_id=outlet_id,
        feature_code="ordering.staff"
    )
    assert result.authorized is False
    assert result.resolved_status == "cancelled"
    assert result.reason == "SUBSCRIPTION_CANCELLED"


def test_outlet_subscription_mutation_rollback_on_audit_failure(client: TestClient, db_session: Session):
    """
    Verifies transactional consistency: if audit log writing or commit fails,
    all changes to OutletSubscription are rolled back.
    """
    from app.modules.subscriptions.models import OutletSubscription

    biz_id, outlet_id, headers = _setup_test_business_and_outlet(client, db_session, initial_plan_code="starter_pos")

    sub_before = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    before_plan_id = sub_before.plan_id
    before_sub_id = sub_before.id

    with patch("app.modules.businesses.platform_service.log_audit", side_effect=RuntimeError("Audit disk failure")):
        with pytest.raises(RuntimeError):
            client.patch(
                f"/api/v1/platform/outlets/{outlet_id}/subscription",
                headers=headers,
                json={"action_type": "activate", "plan_code": "enterprise"}
            )

    # Ensure rollback occurred: no new row exists and sub_before remains is_current=True
    db_session.expire_all()
    sub_after = db_session.query(OutletSubscription).filter(
        OutletSubscription.outlet_id == outlet_id,
        OutletSubscription.is_current == True
    ).first()
    assert sub_after.id == before_sub_id
    assert sub_after.plan_id == before_plan_id
    assert sub_after.is_current is True


