import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from app.modules.tables.models import DiningTable
from app.modules.outlets.models import Outlet
from app.modules.tables.schemas import TableCreate, TableUpdate
from app.core.errors import NotFoundError, ValidationError


def get_outlet_tables(db: Session, outlet_id: uuid.UUID) -> List[DiningTable]:
    return (
        db.query(DiningTable)
        .filter(DiningTable.outlet_id == outlet_id)
        .order_by(DiningTable.table_number.asc())
        .all()
    )


def create_table(db: Session, outlet_id: uuid.UUID, data: TableCreate) -> DiningTable:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    existing = db.query(DiningTable).filter(
        DiningTable.outlet_id == outlet_id,
        DiningTable.table_number == data.table_number.strip()
    ).first()
    if existing:
        raise ValidationError(f"Table '{data.table_number.strip()}' already exists in this outlet")

    table = DiningTable(
        outlet_id=outlet_id,
        table_number=data.table_number.strip(),
        capacity=data.capacity,
        status="available"
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


def update_table(db: Session, table_id: uuid.UUID, data: TableUpdate) -> DiningTable:
    table = db.query(DiningTable).filter(DiningTable.id == table_id).first()
    if not table:
        raise NotFoundError(f"Table with ID '{table_id}' not found")

    if data.table_number is not None and data.table_number.strip() != table.table_number:
        existing = db.query(DiningTable).filter(
            DiningTable.outlet_id == table.outlet_id,
            DiningTable.table_number == data.table_number.strip(),
            DiningTable.id != table_id
        ).first()
        if existing:
            raise ValidationError(f"Table '{data.table_number.strip()}' already exists in this outlet")
        table.table_number = data.table_number.strip()

    if data.capacity is not None:
        table.capacity = data.capacity

    if data.status is not None:
        if data.status not in ["available", "occupied", "reserved"]:
            raise ValidationError(f"Invalid table status '{data.status}'")
        table.status = data.status

    db.commit()
    db.refresh(table)
    return table
