import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, RequireOutletRole
from app.modules.staff.models import User, OutletMembership
from app.modules.orders.schemas import OrderCreate, OrderOut, OrderStatusUpdate
from app.modules.orders import service as order_service
from app.modules.orders.models import Order
from app.core.errors import NotFoundError, ForbiddenError

router = APIRouter(tags=["orders"])


def _verify_order_membership(db: Session, order_id: uuid.UUID, user_id: uuid.UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID '{order_id}' not found")
    membership = db.query(OutletMembership).filter(
        OutletMembership.outlet_id == order.outlet_id,
        OutletMembership.user_id == user_id
    ).first()
    if not membership:
        raise ForbiddenError("You do not have access to this outlet")
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
    dependencies=[Depends(RequireOutletRole(["owner", "manager", "waiter", "kitchen"]))]
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
    _verify_order_membership(db, order_id=order_id, user_id=current_user.id)
    order = order_service.get_order_by_id(db, order_id=order_id)
    return order_service.serialize_order(order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: uuid.UUID,
    request: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _verify_order_membership(db, order_id=order_id, user_id=current_user.id)
    order = order_service.update_order_status(
        db, order_id=order_id, new_status=request.status
    )
    return order_service.serialize_order(order)
