"""
FastAPI приложение для UI пайплайна.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pipeline import Pipeline
from config.settings import settings
from .routes import router


# Глобальный экземпляр пайплайна
pipeline_instance: Pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Инициализирует пайплайн при запуске.
    """
    global pipeline_instance
    pipeline_instance = Pipeline()
    pipeline_instance.init_database()
    print("Pipeline initialized for API")
    yield
    print("API shutdown")


def create_app() -> FastAPI:
    """Создаёт и настраивает приложение FastAPI."""
    app = FastAPI(
        title="EIS Parser UI",
        description="Интерфейс управления пайплайном обработки закупок",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Настраиваем статику и шаблоны
    base_dir = Path(__file__).parent.parent
    static_dir = base_dir / "web" / "static"
    templates_dir = base_dir / "web" / "templates"
    
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Подключаем роуты
    app.include_router(router)
    
    return app


# Экземпляр для запуска через uvicorn
app = create_app()

def get_pipeline() -> Pipeline:
    """Возвращает глобальный экземпляр пайплайна."""
    if pipeline_instance is None:
        raise RuntimeError("Pipeline not initialized")
    return pipeline_instance
