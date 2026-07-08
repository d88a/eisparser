"""API routers grouped by bounded context."""

from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .health import router as health_router
from .stage2 import router as stage2_router
from .stage3 import router as stage3_router
from .stage4 import router as stage4_router
from .user import router as user_router


router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(stage2_router)
router.include_router(stage3_router)
router.include_router(stage4_router)
router.include_router(user_router)
router.include_router(admin_router)
