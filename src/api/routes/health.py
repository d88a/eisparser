"""Public health-check endpoint."""

from fastapi import APIRouter

from services.health_service import HealthService


router = APIRouter()


@router.get("/api/health")
def get_health():
    from ..app import get_pipeline

    pipeline = get_pipeline()
    return HealthService(pipeline).get_health_payload()
