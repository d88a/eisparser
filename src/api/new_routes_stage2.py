"""
Дополнительные API эндпоинты для Этапа 2.
Добавляются к существующим routes.py.
"""

# ==========================================
# USER API (Этап 2)
# ==========================================

class UserSelectRequest(BaseModel):
    user_id: int
    reg_numbers: List[str]

class UserUnselectRequest(BaseModel):
    user_id: int
    reg_numbers: List[str]

class UserRunStage4Request(BaseModel):
    user_id: int
    top_n: int = 20
    get_details: bool = False


@router.get("/api/user/available_zakupki")
def get_available_zakupki(user_id: int = 1):
    """Возвращает закупки со статусом 'url_ready' (готовые к анализу)."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем закупки с статусом url_ready
    zakupki = pipeline.db_service.zakupki.get_by_status('url_ready')
    
    # Получаем текущие выборки пользователя
    selected_reg_numbers = set(pipeline.db_service.user_selections.get_user_selections(user_id))
    
    # Форматируем данные для UI
    result = []
    for z in zakupki:
        # Получаем AI результаты
        ai_result = pipeline.db.ai_results.get_result(z.reg_number)
        
        result.append({
            "reg_number": z.reg_number,
            "description": z.description,
            "initial_price": z.initial_price,
            "status": z.status,
            "prepared_at": z.prepared_at.isoformat() if z.prepared_at else None,
            "city": ai_result.city if ai_result else None,
            "area": f"{ai_result.area_min_m2}-{ai_result.area_max_m2}" if ai_result else None,
            "rooms": ai_result.rooms if ai_result else None,
            "is_selected": z.reg_number in selected_reg_numbers
        })
    
    return {"zakupki": result, "total": len(result)}


@router.post("/api/user/select")
def user_select(req: UserSelectRequest):
    """Добавляет закупки в выборку пользователя."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    added = 0
    for reg_number in req.reg_numbers:
        if pipeline.db_service.user_selections.add_selection(req.user_id, reg_number):
            added += 1
    
    count = pipeline.db_service.user_selections.get_selection_count(req.user_id)
    
    return {
        "status": "ok",
        "added": added,
        "total_selected": count,
        "message": f"Добавлено {added} закупок в выборку"
    }


@router.post("/api/user/unselect")
def user_unselect(req: UserUnselectRequest):
    """Удаляет закупки из выборки пользователя."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    removed = 0
    for reg_number in req.reg_numbers:
        if pipeline.db_service.user_selections.remove_selection(req.user_id, reg_number):
            removed += 1
    
    count = pipeline.db_service.user_selections.get_selection_count(req.user_id)
    
    return {
        "status": "ok",
        "removed": removed,
        "total_selected": count,
        "message": f"Удалено {removed} закупок из выборки"
    }


@router.get("/api/user/selections")
def get_user_selections(user_id: int = 1):
    """Возвращает список выбранных закупок пользователя."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем reg_numbers
    reg_numbers = pipeline.db_service.user_selections.get_user_selections(user_id)
    
    if not reg_numbers:
        return {"zakupki": [], "total": 0}
    
    # Получаем полные данные закупок
    zakupki = pipeline.db_service.zakupki.get_by_reg_numbers(reg_numbers)
    
    result = []
    for z in zakupki:
        ai_result = pipeline.db.ai_results.get_result(z.reg_number)
        
        result.append({
            "reg_number": z.reg_number,
            "description": z.description,
            "initial_price": z.initial_price,
            "status": z.status,
            "city": ai_result.city if ai_result else None,
            "area": f"{ai_result.area_min_m2}-{ai_result.area_max_m2}" if ai_result else None,
            "rooms": ai_result.rooms if ai_result else None,
            "two_gis_url": z.two_gis_url
        })
    
    return {"zakupki": result, "total": len(result)}


@router.post("/api/user/run_stage4")
def user_run_stage4(req: UserRunStage4Request):
    """Запускает Stage 4 (сбор объявлений) для выбранных закупок пользователя."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем выборки пользователя
    reg_numbers = pipeline.db_service.user_selections.get_user_selections(req.user_id)
    
    if not reg_numbers:
        return {"status": "warning", "message": "Нет выбранных закупок"}
    
    # Получаем закупки
    zakupki = pipeline.db_service.zakupki.get_by_reg_numbers(reg_numbers)
    
    # Фильтруем только те, у которых есть two_gis_url
    zakupki_with_url = [z for z in zakupki if z.two_gis_url and z.status == 'url_ready']
    
    if not zakupki_with_url:
        return {"status": "warning", "message": "У выбранных закупок нет ссылок 2ГИС"}
    
    # Запускаем Stage 4 для каждой закупки
    processed = 0
    total_listings = 0
    errors = []
    
    for zakupka in zakupki_with_url:
        try:
            result = pipeline.run_stage4_for_zakupka(
                zakupka.reg_number,
                zakupka.two_gis_url,
                req.top_n,
                req.get_details
            )
            if result.items:
                total_listings += result.actual_n
                processed += 1
        except Exception as e:
            errors.append(f"{zakupka.reg_number}: {str(e)}")
    
    # Очищаем выборку после успешной обработки
    if processed > 0:
        pipeline.db_service.user_selections.clear_user_selections(req.user_id)
    
    return {
        "status": "ok" if processed > 0 else "error",
        "processed": processed,
        "total_listings": total_listings,
        "message": f"Собрано {total_listings} объявлений из {processed} закупок",
        "errors": errors
    }


# ==========================================
# ADMIN API (Этап 2)
# ==========================================

class BatchStage2Request(BaseModel):
    limit: Optional[int] = None

class BatchStage3Request(BaseModel):
    limit: Optional[int] = None


@router.get("/api/admin/pipeline_status")
def get_pipeline_status():
    """Возвращает статистику по статусам закупок."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем статистику по статусам
    status_counts = pipeline.db_service.zakupki.get_status_counts()
    
    # Общее количество
    total = sum(status_counts.values())
    
    return {
        "total_zakupki": total,
        "by_status": status_counts,
        "summary": {
            "ready_for_users": status_counts.get('url_ready', 0),
            "needs_ai": status_counts.get('raw', 0),
            "needs_links": status_counts.get('ai_ready', 0),
            "completed": status_counts.get('listings_fresh', 0)
        }
    }


@router.post("/api/admin/batch_stage2")
def admin_batch_stage2(req: BatchStage2Request):
    """Массовая AI обработка для закупок со статусом 'raw'."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем все закупки со статусом 'raw'
    raw_zakupki = pipeline.db_service.zakupki.get_by_status('raw')
    
    if not raw_zakupki:
        return {"status": "warning", "message": "Нет закупок для AI обработки"}
    
    # Применяем лимит
    if req.limit:
        raw_zakupki = raw_zakupki[:req.limit]
    
    # Получаем reg_numbers
    reg_numbers = [z.reg_number for z in raw_zakupki]
    
    # Запускаем Stage 2
    result = pipeline.run_stage2(reg_numbers=reg_numbers)
    
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "total_available": len(raw_zakupki),
        "errors": result.errors
    }


@router.post("/api/admin/batch_stage3")
def admin_batch_stage3(req: BatchStage3Request):
    """Массовая генерация ссылок для закупок со статусом 'ai_ready'."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # Получаем все закупки со статусом 'ai_ready'
    ai_ready_zakupki = pipeline.db_service.zakupki.get_by_status('ai_ready')
    
    if not ai_ready_zakupki:
        return {"status": "warning", "message": "Нет закупок для генерации ссылок"}
    
    # Применяем лимит
    if req.limit:
        ai_ready_zakupki = ai_ready_zakupki[:req.limit]
    
    # Получаем reg_numbers
    reg_numbers = [z.reg_number for z in ai_ready_zakupki]
    
    # Запускаем Stage 3
    result = pipeline.run_stage3(reg_numbers=reg_numbers)
    
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "generated": result.data.get("generated", 0),
        "total_available": len(ai_ready_zakupki),
        "errors": result.errors
    }
