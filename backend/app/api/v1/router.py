from fastapi import APIRouter
from app.api.v1.public_menu import router as public_menu_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin_menu import router as admin_menu_router

api_router = APIRouter()
api_router.include_router(public_menu_router)
api_router.include_router(auth_router)
api_router.include_router(admin_menu_router)

