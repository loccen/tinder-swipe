"""
API 路由
"""
from fastapi import APIRouter

from app.api.tasks import router as tasks_router
from app.api.dashboard import router as dashboard_router
from app.api.internal import router as internal_router
from app.api.settings import router as settings_router

api_router = APIRouter(prefix="/api")

api_router.include_router(tasks_router)
api_router.include_router(dashboard_router)
api_router.include_router(internal_router)
api_router.include_router(settings_router)
