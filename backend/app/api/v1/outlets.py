import uuid
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import RequireOutletEntitlement
from app.modules.outlets.schemas import OutletBrandingUpdate, OutletBrandingOut
from app.modules.outlets import service as outlet_service

router = APIRouter(prefix="/outlets", tags=["outlets"])


@router.patch(
    "/{outlet_id}/branding",
    response_model=OutletBrandingOut,
    dependencies=[Depends(RequireOutletEntitlement(["owner", "manager"], "menu.digital", write=True))]
)
def update_outlet_branding(
    outlet_id: uuid.UUID,
    data: OutletBrandingUpdate,
    db: Session = Depends(get_db)
):
    outlet = outlet_service.update_outlet_branding(db, outlet_id=outlet_id, data=data)
    return OutletBrandingOut.model_validate(outlet)


@router.post(
    "/{outlet_id}/branding/logo",
    response_model=OutletBrandingOut,
    dependencies=[Depends(RequireOutletEntitlement(["owner", "manager"], "menu.digital", write=True))]
)
async def upload_outlet_logo(
    outlet_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()
    outlet = outlet_service.upload_outlet_branding_image(
        db=db,
        outlet_id=outlet_id,
        image_type="logo",
        file_bytes=file_bytes,
        filename=file.filename or "logo.png"
    )
    return OutletBrandingOut.model_validate(outlet)


@router.post(
    "/{outlet_id}/branding/cover",
    response_model=OutletBrandingOut,
    dependencies=[Depends(RequireOutletEntitlement(["owner", "manager"], "menu.digital", write=True))]
)
async def upload_outlet_cover(
    outlet_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()
    outlet = outlet_service.upload_outlet_branding_image(
        db=db,
        outlet_id=outlet_id,
        image_type="cover",
        file_bytes=file_bytes,
        filename=file.filename or "cover.png"
    )
    return OutletBrandingOut.model_validate(outlet)
