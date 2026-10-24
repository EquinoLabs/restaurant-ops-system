import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
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
from app.modules.orders.schemas import OrderCreate, OrderOut, OrderStatusUpdate, OrderSettlementRequest
from app.modules.orders import service as order_service
from app.modules.orders.models import Order
from app.core.errors import NotFoundError

router = APIRouter(tags=["orders"])


def _verify_order_membership(
    db: Session,
    order_id: uuid.UUID,
    user: User,
    allowed_roles: Optional[List[str]] = None,
    write: bool = False
) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID '{order_id}' not found")
    # Anti-probing: callers with no relationship to the order's outlet get the same
    # not-found response as a missing order (no cross-tenant existence oracle).
    if not has_outlet_relationship(db, order.outlet_id, user.id):
        raise NotFoundError(f"Order with ID '{order_id}' not found")
    roles = allowed_roles if allowed_roles is not None else ["owner", "manager", "waiter", "kitchen"]
    verify_subresource_outlet_access(
        db,
        order.outlet_id,
        user,
        allowed_roles=roles,
        feature_code="ordering.staff",
        write=write
    )
    return order


@router.get(
    "/outlets/{outlet_id}/orders",
    response_model=List[OrderOut],
    dependencies=[Depends(RequireOutletRole(["owner", "manager", "waiter", "kitchen"]))]
)
def get_orders(
    outlet_id: uuid.UUID,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    orders = order_service.get_outlet_orders(db, outlet_id=outlet_id, status=status)
    return [order_service.serialize_order(o) for o in orders]


@router.post(
    "/outlets/{outlet_id}/orders",
    response_model=OrderOut,
    dependencies=[Depends(RequireOutletEntitlement(["owner", "manager", "waiter", "kitchen"], "ordering.staff"))]
)
def create_order(
    outlet_id: uuid.UUID,
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = order_service.create_order(
        db, outlet_id=outlet_id, waiter_id=current_user.id, data=data
    )
    return order_service.serialize_order(order)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_order_membership(db, order_id=order_id, user=current_user)
    order = order_service.get_order_by_id(db, order_id=order_id)
    return order_service.serialize_order(order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: uuid.UUID,
    request: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_order_membership(db, order_id=order_id, user=current_user, write=True)
    order = order_service.update_order_status(
        db, order_id=order_id, new_status=request.status
    )
    return order_service.serialize_order(order)


@router.post("/orders/{order_id}/settle", response_model=OrderOut)
def settle_order(
    order_id: uuid.UUID,
    request: OrderSettlementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Explicitly settle an order's bill with cash or UPI.

    Restricted to authorized staff roles (owner, manager, waiter).
    Kitchen role cannot settle bills.
    """
    _verify_order_membership(
        db,
        order_id=order_id,
        user=current_user,
        allowed_roles=["owner", "manager", "waiter"],
        write=True
    )
    order = order_service.settle_order(
        db,
        order_id=order_id,
        settling_user=current_user,
        payment_method=request.payment_method,
        confirm=request.confirm
    )
    return order_service.serialize_order(order)
