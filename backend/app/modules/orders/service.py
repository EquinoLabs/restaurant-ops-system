import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.modules.orders.models import Order, OrderItem
from app.modules.tables.models import DiningTable
from app.modules.menus.models import MenuItem
from app.modules.outlets.models import Outlet
from app.modules.orders.schemas import OrderCreate, OrderOut, OrderItemOut
from app.core.errors import NotFoundError, ValidationError


def generate_order_number(db: Session, outlet_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    count = (
        db.query(Order)
        .filter(
            Order.outlet_id == outlet_id,
            Order.created_at >= datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        )
        .count()
    )
    return f"ORD-{date_str}-{(count + 1):03d}"


def create_order(
    db: Session,
    outlet_id: uuid.UUID,
    waiter_id: uuid.UUID,
    data: OrderCreate
) -> Order:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise NotFoundError(f"Outlet with ID '{outlet_id}' not found")

    table = None
    if data.table_id:
        table = db.query(DiningTable).filter(
            DiningTable.id == data.table_id,
            DiningTable.outlet_id == outlet_id
        ).first()
        if not table:
            raise ValidationError(f"Table with ID '{data.table_id}' not found in this outlet")

    if not data.items:
        raise ValidationError("Order must contain at least one item")

    order_number = generate_order_number(db, outlet_id=outlet_id)

    order = Order(
        outlet_id=outlet_id,
        table_id=table.id if table else None,
        waiter_user_id=waiter_id,
        order_number=order_number,
        status="pending",
        order_type=data.order_type,
        total_amount=Decimal("0.00"),
        notes=data.notes.strip() if data.notes else None
    )
    db.add(order)
    db.flush()

    total_amount = Decimal("0.00")
    for req_item in data.items:
        if req_item.quantity <= 0:
            raise ValidationError("Item quantity must be at least 1")

        menu_item = db.query(MenuItem).filter(
            MenuItem.id == req_item.menu_item_id,
            MenuItem.outlet_id == outlet_id
        ).first()

        if not menu_item:
            raise ValidationError(f"Menu item with ID '{req_item.menu_item_id}' not found in this outlet")
        if not menu_item.is_active:
            raise ValidationError(f"Menu item '{menu_item.name}' is archived and cannot be ordered")
        if not menu_item.is_available:
            raise ValidationError(f"Menu item '{menu_item.name}' is currently out of stock")

        unit_price = menu_item.price
        subtotal = unit_price * Decimal(req_item.quantity)
        total_amount += subtotal

        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            item_name=menu_item.name,
            unit_price=unit_price,
            quantity=req_item.quantity,
            subtotal=subtotal,
            special_instructions=req_item.special_instructions.strip() if req_item.special_instructions else None
        )
        db.add(order_item)

    order.total_amount = total_amount

    # Auto-update table status to occupied for dine-in orders
    if table and data.order_type == "dine_in":
        table.status = "occupied"

    db.commit()

    # Re-query order with relationships loaded
    full_order = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.table),
            joinedload(Order.waiter)
        )
        .filter(Order.id == order.id)
        .first()
    )
    return full_order


def get_outlet_orders(
    db: Session,
    outlet_id: uuid.UUID,
    status: Optional[str] = None
) -> List[Order]:
    query = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.table),
            joinedload(Order.waiter)
        )
        .filter(Order.outlet_id == outlet_id)
    )

    if status and status.strip():
        query = query.filter(Order.status == status.strip())

    return query.order_by(Order.created_at.desc()).all()


def get_order_by_id(db: Session, order_id: uuid.UUID) -> Order:
    order = (
        db.query(Order)
        .options(
            joinedload(Order.items),
            joinedload(Order.table),
            joinedload(Order.waiter)
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise NotFoundError(f"Order with ID '{order_id}' not found")
    return order


def update_order_status(
    db: Session,
    order_id: uuid.UUID,
    new_status: str
) -> Order:
    valid_statuses = ["pending", "confirmed", "in_kitchen", "served", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise ValidationError(f"Invalid status '{new_status}'. Allowed: {', '.join(valid_statuses)}")

    order = get_order_by_id(db, order_id=order_id)
    order.status = new_status

    # Free up table status when order is completed or cancelled
    if new_status in ["completed", "cancelled"] and order.table_id:
        active_orders = (
            db.query(Order)
            .filter(
                Order.table_id == order.table_id,
                Order.id != order_id,
                Order.status.in_(["pending", "confirmed", "in_kitchen", "served"])
            )
            .count()
        )
        if active_orders == 0 and order.table:
            order.table.status = "available"

    db.commit()
    db.refresh(order)
    return order


def serialize_order(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        outlet_id=order.outlet_id,
        table_id=order.table_id,
        table_number=order.table.table_number if order.table else None,
        waiter_user_id=order.waiter_user_id,
        waiter_name=order.waiter.display_name if order.waiter else None,
        order_number=order.order_number,
        status=order.status,
        order_type=order.order_type,
        total_amount=order.total_amount,
        notes=order.notes,
        items=[
            OrderItemOut(
                id=item.id,
                menu_item_id=item.menu_item_id,
                item_name=item.item_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal,
                special_instructions=item.special_instructions
            )
            for item in order.items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at
    )
