import uuid
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OutletMembershipOut(BaseModel):
    outlet_id: uuid.UUID
    outlet_name: str
    public_slug: str
    business_id: uuid.UUID
    business_name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class UserMeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    is_platform_admin: bool = False
    platform_role: Optional[str] = None
    memberships: List[OutletMembershipOut]

    model_config = ConfigDict(from_attributes=True)


# Alias for compatibility with architecture specification nomenclature
UserProfile = UserMeOut



class StaffCreateRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
