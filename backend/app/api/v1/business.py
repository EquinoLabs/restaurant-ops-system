from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import RequireBusinessOwner
from app.modules.businesses.models import Business
from app.modules.subscriptions.schemas import OwnerSubscriptionSummaryOut
from app.modules.subscriptions.service import EntitlementService

router = APIRouter(prefix="/business", tags=["business"])


@router.get("/subscription", response_model=OwnerSubscriptionSummaryOut)
def get_owner_subscription(
    business: Business = Depends(RequireBusinessOwner()),
    db: Session = Depends(get_db)
):
    """
    Returns the read-only subscription summary and outlet capacity usage for the caller's business.
    Protected strictly by RequireBusinessOwner: only active accounts with role 'owner' in the
    resolved business may access this endpoint.
    """
    return EntitlementService.get_owner_subscription_summary(
        db=db,
        business_id=business.id
    )
