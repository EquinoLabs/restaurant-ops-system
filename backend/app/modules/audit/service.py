import uuid
from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session, joinedload
from app.modules.audit.models import AuditLog


def log_audit(
    db: Session,
    business_id: Optional[uuid.UUID] = None,
    outlet_id: Optional[uuid.UUID] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    action: str = "",
    entity_type: str = "",
    entity_id: Optional[uuid.UUID] = None,
    metadata_json: Optional[Dict[str, Any]] = None
) -> AuditLog:
    log_entry = AuditLog(
        business_id=business_id,
        outlet_id=outlet_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata_json
    )
    db.add(log_entry)
    db.flush()
    return log_entry


def get_outlet_audit_logs(
    db: Session,
    outlet_id: uuid.UUID,
    limit: int = 50
) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .options(joinedload(AuditLog.actor))
        .filter(AuditLog.outlet_id == outlet_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def list_platform_audit_logs(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    business_id: Optional[uuid.UUID] = None
):
    query = db.query(AuditLog).options(
        joinedload(AuditLog.actor),
        joinedload(AuditLog.business),
        joinedload(AuditLog.outlet),
    )

    if action:
        query = query.filter(AuditLog.action == action.strip())

    if business_id is not None:
        query = query.filter(AuditLog.business_id == business_id)

    total = query.count()

    items = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return items, total

