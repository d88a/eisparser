"""User flow routes."""

from fastapi import APIRouter, Depends

from models.statuses import STAGE4_QUEUE_STATUSES, ZakupkaStatus

from .common import UserRunStage4Request, UserSelectRequest, UserUnselectRequest, user_access_required


router = APIRouter()


@router.get("/api/user/available_zakupki")
def get_available_zakupki(
    user_id: int = 1,
    offset: int = 0,
    limit: int = 10,
    _user_access: bool = Depends(user_access_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    all_zakupki = pipeline.db.zakupki.get_by_status(ZakupkaStatus.URL_READY)
    zakupki = all_zakupki[offset : offset + limit]
    selected_reg_numbers = set(pipeline.db.user_selections.get_user_selections(user_id))
    result = []
    for z in zakupki:
        ai_result = pipeline.ai.get_result(z.reg_number)
        result.append(
            {
                "reg_number": z.reg_number,
                "description": z.description,
                "initial_price": z.initial_price,
                "status": z.status,
                "prepared_at": z.prepared_at.isoformat() if z.prepared_at else None,
                "city": ai_result.city if ai_result else None,
                "area": f"{ai_result.area_min_m2}-{ai_result.area_max_m2}" if ai_result else None,
                "rooms": ai_result.rooms if ai_result else None,
                "is_selected": z.reg_number in selected_reg_numbers,
            }
        )
    return {"zakupki": result, "total": len(all_zakupki), "offset": offset, "limit": limit}


@router.post("/api/user/select")
def user_select(req: UserSelectRequest, _user_access: bool = Depends(user_access_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    added = 0
    for reg_number in req.reg_numbers:
        if pipeline.db.user_selections.add_selection(req.user_id, reg_number):
            added += 1
    count = pipeline.db.user_selections.get_selection_count(req.user_id)
    return {
        "status": "ok",
        "added": added,
        "total_selected": count,
        "message": f"Добавлено {added} закупок в выборку",
    }


@router.post("/api/user/unselect")
def user_unselect(req: UserUnselectRequest, _user_access: bool = Depends(user_access_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    removed = 0
    for reg_number in req.reg_numbers:
        if pipeline.db.user_selections.remove_selection(req.user_id, reg_number):
            removed += 1
    count = pipeline.db.user_selections.get_selection_count(req.user_id)
    return {
        "status": "ok",
        "removed": removed,
        "total_selected": count,
        "message": f"Удалено {removed} закупок из выборки",
    }


@router.get("/api/user/selections")
def get_user_selections(user_id: int = 1, _user_access: bool = Depends(user_access_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    reg_numbers = pipeline.db.user_selections.get_user_selections(user_id)
    if not reg_numbers:
        return {"zakupki": [], "total": 0}
    zakupki = pipeline.db.zakupki.get_by_reg_numbers(reg_numbers)
    result = []
    for z in zakupki:
        ai_result = pipeline.ai.get_result(z.reg_number)
        result.append(
            {
                "reg_number": z.reg_number,
                "description": z.description,
                "initial_price": z.initial_price,
                "status": z.status,
                "city": ai_result.city if ai_result else None,
                "area": f"{ai_result.area_min_m2}-{ai_result.area_max_m2}" if ai_result else None,
                "rooms": ai_result.rooms if ai_result else None,
                "two_gis_url": z.two_gis_url,
            }
        )
    return {"zakupki": result, "total": len(result)}


@router.post("/api/user/run_stage4")
def user_run_stage4(req: UserRunStage4Request, _user_access: bool = Depends(user_access_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    reg_numbers = pipeline.db.user_selections.get_user_selections(req.user_id)
    if not reg_numbers:
        return {"status": "warning", "message": "Нет выбранных закупок"}

    zakupki = pipeline.db.zakupki.get_by_reg_numbers(reg_numbers)
    zakupki_with_url = [z for z in zakupki if z.two_gis_url and z.status in STAGE4_QUEUE_STATUSES]
    if not zakupki_with_url:
        return {"status": "warning", "message": "ссылки нет или закупки еще не готовы к Stage 4"}

    processed = 0
    total_listings = 0
    errors = []
    successful_reg_numbers = []
    for zakupka in zakupki_with_url:
        try:
            result = pipeline.run_stage4_for_zakupka(
                zakupka.reg_number,
                zakupka.two_gis_url,
                req.top_n,
                req.get_details,
            )
            if result.error:
                errors.append(f"{zakupka.reg_number}: {result.error}")
            else:
                processed += 1
                total_listings += result.actual_n
                successful_reg_numbers.append(zakupka.reg_number)
            pipeline.logger.info(
                "stage_progress reg_number=%s stage=4 result=%s reason=%s",
                zakupka.reg_number,
                "error" if result.error else "ok",
                result.error or f"listings={result.actual_n}",
            )
        except Exception as e:
            errors.append(f"{zakupka.reg_number}: {str(e)}")
            pipeline.db.zakupki.update_status(zakupka.reg_number, ZakupkaStatus.STAGE4_ERROR)
            pipeline.logger.info(
                "stage_progress reg_number=%s stage=4 result=error reason=%s",
                zakupka.reg_number,
                e,
            )

    if successful_reg_numbers:
        for reg_number in successful_reg_numbers:
            pipeline.db.user_selections.remove_selection(req.user_id, reg_number)

    return {
        "status": "ok" if processed > 0 and not errors else ("warning" if processed > 0 else "error"),
        "processed": processed,
        "total_listings": total_listings,
        "message": f"Собрано {total_listings} объявлений из {processed} закупок",
        "errors": errors,
    }
