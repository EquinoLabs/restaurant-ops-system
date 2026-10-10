from typing import Optional
from fastapi import APIRouter, Depends, Response, Request, Header, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.menus.schemas import PublicOutletMenuResponse
from app.modules.menus.service import get_public_menu_by_slug, generate_outlet_qr_code
from app.modules.orders.schemas import PublicOrderCreate, OrderOut
from app.modules.orders.service import create_public_order, serialize_order

router = APIRouter(prefix="/public", tags=["Public Menu"])


@router.get(
    "/outlets/{slug}/menu",
    response_model=PublicOutletMenuResponse,
    summary="Get active public menu for an outlet by QR slug"
)
def get_public_menu(slug: str, db: Session = Depends(get_db)):
    return get_public_menu_by_slug(db=db, public_slug=slug)


@router.get(
    "/outlets/{slug}/qr",
    summary="Generate permanent scannable PNG QR code for an outlet",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Returns high-resolution PNG image of the permanent outlet QR code."
        }
    }
)
def get_outlet_qr_code(
    slug: str,
    download: bool = False,
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Determine origin or default frontend URL
    origin = request.headers.get("origin") if request else None
    base_url = origin if origin else "http://localhost:5173"

    qr_bytes = generate_outlet_qr_code(db=db, public_slug=slug, base_url=base_url)

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{slug}-qr-code.png"'

    return Response(content=qr_bytes, media_type="image/png", headers=headers)


@router.post(
    "/outlets/{slug}/orders",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer QR / self-service order"
)
def create_customer_order(
    slug: str,
    data: PublicOrderCreate,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db)
):
    order = create_public_order(
        db=db,
        public_slug=slug,
        data=data,
        idempotency_key_header=x_idempotency_key
    )
    return serialize_order(order)

