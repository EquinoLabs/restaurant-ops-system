import uuid
import json
import hashlib
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.modules.orders.models import Order, OrderItem, OrderIdempotencyKey
from app.modules.tables.models import DiningTable
from app.modules.menus.models import MenuItem
from app.modules.outlets.models import Outlet
from app.modules.orders.schemas import OrderCreate, OrderOut, OrderItemOut, PublicOrderCreate
from app.core.errors import NotFoundError, NotFoundException, ValidationError, BusinessRuleException, APIException



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


def compute_request_hash(data: PublicOrderCreate) -> str:
    sorted_items = sorted(data.items, key=lambda i: str(i.menu_item_id))
    normalized_items = [
        {
            "menu_item_id": str(item.menu_item_id),
            "quantity": item.quantity,
            "special_instructions": item.special_instructions.strip() if item.special_instructions else None
        }
        for item in sorted_items
    ]
    normalized = {
        "table_number": data.table_number.strip() if data.table_number else None,
        "order_type": data.order_type.strip().lower() if data.order_type else None,
        "notes": data.notes.strip() if data.notes else None,
        "items": normalized_items
    }
    canonical_json = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def create_public_order(
    db: Session,
    public_slug: str,
    data: PublicOrderCreate,
    idempotency_key_header: Optional[str] = None
) -> Order:
    # 1. Resolve and validate idempotency key consistency
    header_key = (idempotency_key_header or "").strip()
    body_key = (data.idempotency_key or "").strip()

    if header_key and body_key and header_key != body_key:
        raise BusinessRuleException(
            code="IDEMPOTENCY_KEY_MISMATCH",
            message="Conflicting idempotency keys provided in header and payload."
        )

    idempotency_key = header_key or body_key or None

    # 2. Resolve active Outlet & Business
    outlet = (
        db.query(Outlet)
        .filter(Outlet.public_slug == public_slug, Outlet.status == "active")
        .first()
    )
    if not outlet or not outlet.business or outlet.business.status != "active":
        raise NotFoundException(
            code="OUTLET_NOT_FOUND",
            message=f"Outlet with slug '{public_slug}' was not found or is inactive."
        )

    # Subscription/entitlement gate: ordering requires an entitled plan and a live
    # subscription status (expired/cancelled subscriptions keep read-only public menu
    # browsing but must not accept orders). Public callers must not learn suspension
    # or subscription state, so denials reuse the uniform not-found response.
    from app.modules.subscriptions.service import EntitlementService
    entitlement = EntitlementService.check_entitlement(
        db=db,
        business_id=outlet.business_id,
        feature_code="ordering.customer",
        outlet_id=outlet.id
    )
    if not entitlement.authorized:
        raise NotFoundException(
            code="OUTLET_NOT_FOUND",
            message=f"Outlet with slug '{public_slug}' was not found or is inactive."
        )

    request_hash = compute_request_hash(data)

    # 3. Check idempotency key if provided
    if idempotency_key:
        existing_idemp = (
            db.query(OrderIdempotencyKey)
            .filter(
                OrderIdempotencyKey.outlet_id == outlet.id,
                OrderIdempotencyKey.idempotency_key == idempotency_key
            )
            .first()
        )
        if existing_idemp:
            if existing_idemp.request_hash == request_hash:
                return get_order_by_id(db, existing_idemp.order_id)
            else:
                raise APIException(
                    status_code=409,
                    code="IDEMPOTENCY_CONFLICT",
                    message="Idempotency key reused with a different payload"
                )

    # 4. Validate Table if table_number provided
    table = None
    if data.table_number and data.table_number.strip():
        table_num = data.table_number.strip()
        table = (
            db.query(DiningTable)
            .filter(
                DiningTable.outlet_id == outlet.id,
                DiningTable.table_number == table_num
            )
            .first()
        )
        if not table:
            raise BusinessRuleException(
                code="INVALID_TABLE",
                message=f"Table '{table_num}' was not found in this outlet."
            )

    # 5. Determine order_type
    order_type = "dine_in" if table else "takeaway"
    if data.order_type and data.order_type.strip():
        req_type = data.order_type.strip().lower()
        if req_type not in ["dine_in", "takeaway", "delivery"]:
            raise ValidationError(
                code="INVALID_ORDER_TYPE",
                message=f"Invalid order type '{req_type}'. Allowed: dine_in, takeaway, delivery"
            )
        order_type = req_type

    # 6. Validate items and combine duplicates
    if not data.items:
        raise ValidationError(code="VALIDATION_ERROR", message="Order must contain at least one item")

    item_quantities = {}
    item_instructions = {}
    for req_item in data.items:
        item_id = req_item.menu_item_id
        if req_item.quantity <= 0:
            raise ValidationError(code="INVALID_QUANTITY", message="Item quantity must be at least 1")
        item_quantities[item_id] = item_quantities.get(item_id, 0) + req_item.quantity
        if item_quantities[item_id] > 99:
            raise ValidationError(code="EXCESSIVE_QUANTITY", message="Item quantity cannot exceed 99")
        if req_item.special_instructions and req_item.special_instructions.strip():
            inst = req_item.special_instructions.strip()
            if item_id in item_instructions and item_instructions[item_id]:
                item_instructions[item_id] += f"; {inst}"
            else:
                item_instructions[item_id] = inst

    validated_items = []
    total_amount = Decimal("0.00")

    for item_id, qty in item_quantities.items():
        menu_item = (
            db.query(MenuItem)
            .filter(MenuItem.id == item_id, MenuItem.outlet_id == outlet.id)
            .first()
        )
        if not menu_item:
            raise BusinessRuleException(
                code="INVALID_MENU_ITEM",
                message=f"Menu item with ID '{item_id}' not found in this outlet."
            )
        if not menu_item.is_active or not menu_item.is_available:
            raise BusinessRuleException(
                code="ITEM_UNAVAILABLE",
                message=f"Menu item '{menu_item.name}' is currently unavailable for ordering."
            )

        unit_price = menu_item.price
        subtotal = unit_price * Decimal(qty)
        total_amount += subtotal

        validated_items.append({
            "menu_item": menu_item,
            "unit_price": unit_price,
            "quantity": qty,
            "subtotal": subtotal,
            "special_instructions": item_instructions.get(item_id)
        })

    # 7. Create Order & Items atomically with targeted collision recovery
    max_retries = 3
    created_order_id = None

    for attempt in range(max_retries):
        try:
            if attempt == 0:
                order_number = generate_order_number(db, outlet_id=outlet.id)
            else:
                now = datetime.now(timezone.utc)
                date_str = now.strftime("%Y%m%d")
                count = (
                    db.query(Order)
                    .filter(
                        Order.outlet_id == outlet.id,
                        Order.created_at >= datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                    )
                    .count()
                )
                order_number = f"ORD-{date_str}-{(count + 1 + attempt):03d}"

            order = Order(
                outlet_id=outlet.id,
                table_id=table.id if table else None,
                waiter_user_id=None,
                order_number=order_number,
                status="pending",
                order_type=order_type,
                total_amount=total_amount,
                notes=data.notes.strip() if data.notes else None
            )
            db.add(order)
            db.flush()

            for v_item in validated_items:
                order_item = OrderItem(
                    order_id=order.id,
                    menu_item_id=v_item["menu_item"].id,
                    item_name=v_item["menu_item"].name,
                    unit_price=v_item["unit_price"],
                    quantity=v_item["quantity"],
                    subtotal=v_item["subtotal"],
                    special_instructions=v_item["special_instructions"]
                )
                db.add(order_item)

            if table and order_type == "dine_in":
                table.status = "occupied"

            if idempotency_key:
                idemp = OrderIdempotencyKey(
                    outlet_id=outlet.id,
                    idempotency_key=idempotency_key,
                    order_id=order.id,
                    request_hash=request_hash
                )
                db.add(idemp)

            db.commit()
            created_order_id = order.id
            break
        except IntegrityError as ie:
            db.rollback()
            err_str = str(ie.orig) if hasattr(ie, 'orig') else str(ie)

            # Check if it was an order_number uniqueness collision
            if "uq_outlet_order_number" in err_str or "orders.outlet_id, orders.order_number" in err_str or "orders.order_number" in err_str:
                if attempt < max_retries - 1:
                    continue

            # Check if it was an idempotency key conflict
            if idempotency_key:
                existing_key = (
                    db.query(OrderIdempotencyKey)
                    .filter(
                        OrderIdempotencyKey.outlet_id == outlet.id,
                        OrderIdempotencyKey.idempotency_key == idempotency_key
                    )
                    .first()
                )
                if existing_key:
                    if existing_key.request_hash == request_hash:
                        return get_order_by_id(db, existing_key.order_id)
                    else:
                        raise APIException(
                            status_code=409,
                            code="IDEMPOTENCY_CONFLICT",
                            message="Idempotency key reused with a different payload"
                        )
            raise ie
        except Exception as e:
            db.rollback()
            raise e

    return get_order_by_id(db, created_order_id)


