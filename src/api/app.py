"""FastAPI application for the UI pipeline."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from pipeline import Pipeline
from .routes import router


pipeline_instance: Pipeline = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize pipeline once on application startup."""
    fail_fast = (os.getenv("ADMIN_SECURITY_FAIL_FAST", "false").strip().lower() == "true")
    settings.validate_admin_security(fail_fast=fail_fast)

    global pipeline_instance
    pipeline_instance = Pipeline()
    pipeline_instance.init_database()
    print("Pipeline initialized for API")
    yield
    print("API shutdown")


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    app = FastAPI(
        title="EIS Parser UI",
        description="Интерфейс управления пайплайном обработки закупок",
        version="1.0.0",
        lifespan=lifespan,
    )

    base_dir = Path(__file__).parent.parent
    static_dir = base_dir / "web" / "static"

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(router)
    return app


app = create_app()


def get_pipeline() -> Pipeline:
    """Return global pipeline instance initialized in app lifespan."""
    if pipeline_instance is None:
        raise RuntimeError("Pipeline not initialized")
    return pipeline_instance
