from fastapi import APIRouter
from app.api.v1.public_menu import router as public_menu_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin_menu import router as admin_menu_router
from app.api.v1.tables import router as tables_router
from app.api.v1.orders import router as orders_router
from app.api.v1.platform import router as platform_router

api_router = APIRouter()
api_router.include_router(public_menu_router)
api_router.include_router(auth_router)
api_router.include_router(admin_menu_router)
api_router.include_router(tables_router)
api_router.include_router(orders_router)
api_router.include_router(platform_router)


