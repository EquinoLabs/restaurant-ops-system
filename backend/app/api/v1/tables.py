import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import (
    get_current_user,
    RequireOutletRole,
    RequireOutletEntitlement,
    has_outlet_relationship,
    verify_subresource_outlet_access,
)
from app.modules.staff.models import User
from app.modules.tables.schemas import TableCreate, TableUpdate, TableOut
from app.modules.tables import service as table_service
from app.modules.tables.models import DiningTable
from app.core.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["tables"])


def _verify_table_membership(db: Session, table_id: uuid.UUID, user: User) -> DiningTable:
    table = db.query(DiningTable).filter(DiningTable.id == table_id).first()
    if not table:
        raise NotFoundError(f"Table with ID '{table_id}' not found")
    # Anti-probing: callers with no relationship to the table's outlet get the same
    # not-found response as a missing table (no cross-tenant existence oracle).
    if not has_outlet_relationship(db, table.outlet_id, user.id):
        raise NotFoundError(f"Table with ID '{table_id}' not found")
    membership = verify_subresource_outlet_access(
        db,
        table.outlet_id,
        user,
        allowed_roles=["owner", "manager", "waiter", "kitchen"],
        feature_code="ordering.staff"
    )
    if membership.role not in ["owner", "manager"]:
        raise ForbiddenError(f"Role '{membership.role}' is not authorized to modify tables")
    return table


@router.get(
    "/outlets/{outlet_id}/tables",
    response_model=List[TableOut],
    dependencies=[Depends(RequireOutletRole(["owner", "manager", "waiter", "kitchen"]))]
)
def get_tables(outlet_id: uuid.UUID, db: Session = Depends(get_db)):
    tables = table_service.get_outlet_tables(db, outlet_id=outlet_id)
    return [TableOut.model_validate(t) for t in tables]


@router.post(
    "/outlets/{outlet_id}/tables",
    response_model=TableOut,
    dependencies=[Depends(RequireOutletEntitlement(["owner", "manager"], "ordering.staff"))]
)
def create_table(
    outlet_id: uuid.UUID,
    data: TableCreate,
    db: Session = Depends(get_db)
):
    table = table_service.create_table(db, outlet_id=outlet_id, data=data)
    return TableOut.model_validate(table)


@router.patch("/tables/{table_id}", response_model=TableOut)
def update_table(
    table_id: uuid.UUID,
    data: TableUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_table_membership(db, table_id=table_id, user=current_user)
    table = table_service.update_table(db, table_id=table_id, data=data)
    return TableOut.model_validate(table)
