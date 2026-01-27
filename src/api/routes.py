"""
API Роуты для UI.
"""
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from services.view_service import ViewService
from models.decision import Decision

router = APIRouter()

# Шаблоны
base_dir = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(base_dir / "web" / "templates"))

# Pydantic models
class DecisionRequest(BaseModel):
    user_id: int
    reg_number: str
    stage: int
    decision: str
    comment: Optional[str] = None

class RunStage1Request(BaseModel):
    limit: int = 10

class RunStage2Request(BaseModel):
    user_id: int


@router.get("/")
def read_root(request: Request):
    """Главная страница (Stage 1)."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/stage1")
def get_stage1_data(user_id: int = 1, limit: int = 10): # Hardcoded user_id for MVP
    """Получает данные для таблицы Stage 1."""
    # Ленивый импорт, чтобы избежать циклических зависимостей при старте
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    view_service = ViewService(pipeline.db)
    # Используем stage=1
    data = view_service.get_zakupka_stage_view(user_id, 1, limit=limit)
    return data


@router.post("/api/actions/run_stage1")
def run_stage1(req: RunStage1Request):
    """Запускает Stage 1 (Загрузка данных)."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    result = pipeline.run_stage1(limit=req.limit)
    
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "data": result.data,
        "errors": result.errors
    }


class AddToStage2Request(BaseModel):
    user_id: int
    reg_numbers: List[str]

@router.post("/api/actions/add_to_stage2")
def add_to_stage2(req: AddToStage2Request):
    """Добавляет выбранные закупки в Stage 2 (ИИ-анализ)."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    count = 0
    for reg_number in req.reg_numbers:
        decision = Decision(
            user_id=req.user_id,
            reg_number=reg_number,
            stage=1,
            decision='selected',  # Mark as selected for Stage 2
            comment=None
        )
        if pipeline.db.decisions.save(decision):
            count += 1
    
    # Trigger AI processing for these items
    if count > 0:
        result = pipeline.run_stage2(reg_numbers=req.reg_numbers)
        return {
            "status": "ok",
            "count": count,
            "message": f"Добавлено {count} закупок, ИИ-анализ: {result.message}"
        }
    
    return {"status": "warning", "count": 0, "message": "Ни одна закупка не была добавлена"}


@router.post("/api/decisions")
def save_decision(decision_data: DecisionRequest):
    """Сохраняет решение пользователя."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    decision = Decision(
        user_id=decision_data.user_id,
        reg_number=decision_data.reg_number,
        stage=decision_data.stage,
        decision=decision_data.decision,
        comment=decision_data.comment
    )
    
    success = pipeline.db.decisions.save(decision)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save decision")
    
    return {"status": "ok", "decision": decision.decision}


class RunStage2Request(BaseModel):
    user_id: int
    reg_numbers: Optional[List[str]] = None # Optional explicit list

@router.post("/api/actions/run_stage2")
def run_stage2(req: RunStage2Request):
    """Запускает Stage 2 для одобренных закупок."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # 1. Получаем approved для Stage 1 (Global list for security check)
    all_approved = set(pipeline.db.decisions.get_approved_reg_numbers(req.user_id, 1))
    
    target_ids = []
    
    if req.reg_numbers:
        # Filter: Take only those from request that are actually approved
        target_ids = [r for r in req.reg_numbers if r in all_approved]
        if len(target_ids) < len(req.reg_numbers):
            # Log warning if some requested IDs were not approved
            print(f"Warning: Ignored {len(req.reg_numbers) - len(target_ids)} non-approved items")
    else:
        # Fallback: Process all approved
        target_ids = list(all_approved)
    
    if not target_ids:
        return {"status": "warning", "message": "Нет одобренных закупок для запуска (выберите их галочками)"}
    
    # 2. Запускаем pipeline.run_stage2 c фильтром
    result = pipeline.run_stage2(reg_numbers=target_ids)
    
    return {
        "status": "ok" if result.success else "error", 
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "errors": result.errors
    }



# ==========================================
# STAGE 2 ENDPOINTS
# ==========================================

@router.get("/stage2")
def read_stage2(request: Request):
    """Страница Stage 2 (AI Review)."""
    return templates.TemplateResponse("stage2.html", {"request": request})

@router.get("/api/stage2")
def get_stage2_data(user_id: int = 1):
    """Получает данные для проверки AI (Stage 2)."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    view_service = ViewService(pipeline.db)
    
    # 2 = Stage 2
    data = view_service.get_zakupka_stage_view(user_id, 2)
    return data

class RunStage3Request(BaseModel):
    user_id: int

@router.post("/api/actions/run_stage3")
def run_stage3(req: RunStage3Request):
    """Запускает Stage 3 (Генерация ссылок) для одобренных на Stage 2."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # 1. Получаем approved для Stage 2
    approved_ids = pipeline.db.decisions.get_approved_reg_numbers(req.user_id, 2)
    
    if not approved_ids:
        return {"status": "warning", "message": "Нет одобренных на 2 этапе закупок"}
    
    # 2. Запускаем
    result = pipeline.run_stage3(reg_numbers=approved_ids)
    
    return {
        "status": "ok" if result.success else "error", 
        "message": result.message,
        "generated": result.data.get("generated", 0),
        "errors": result.errors
    }


# ==========================================
# OVERRIDES API
# ==========================================

class OverrideRequest(BaseModel):
    user_id: int
    reg_number: str
    field_name: str
    value: str

@router.post("/api/overrides")
def save_override(req: OverrideRequest):
    """Сохраняет пользовательское переопределение AI-поля."""
    from .app import get_pipeline
    from models.user_override import UserOverride
    
    pipeline = get_pipeline()
    
    override = UserOverride(
        user_id=req.user_id,
        reg_number=req.reg_number,
        field_name=req.field_name,
        value=req.value
    )
    
    if pipeline.db.user_overrides.save(override):
        return {"status": "ok", "message": f"Сохранено: {req.field_name} = {req.value}"}
    
    return {"status": "error", "message": "Не удалось сохранить"}

@router.get("/api/overrides/{reg_number}")
def get_overrides(reg_number: str, user_id: int = 1):
    """Получает все overrides для закупки."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    overrides = pipeline.db.user_overrides.get_for_zakupka(reg_number, user_id)
    return overrides
