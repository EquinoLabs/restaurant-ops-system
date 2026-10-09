from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.modules.staff.schemas import LoginRequest, TokenResponse, UserMeOut
from app.modules.staff.service import authenticate_user, get_user_me_profile
from app.modules.staff.models import User
from app.core.security import create_access_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, email=request.email, password=request.password)
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserMeOut)
@router.get("/auth/me", response_model=UserMeOut)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_user_me_profile(db, user_id=current_user.id)
