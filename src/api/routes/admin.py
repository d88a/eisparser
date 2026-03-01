"""Admin API routes."""

from fastapi import APIRouter, Depends

from models.statuses import ZakupkaStatus

from .common import BatchStage2Request, BatchStage3Request, admin_required


router = APIRouter()


@router.post("/api/admin/cleanup_selected")
def cleanup_selected(admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    removed = pipeline.db.decisions.delete_by_decision_value("selected")
    return {"status": "ok", "removed": removed}


@router.get("/api/admin/pipeline_status")
def get_pipeline_status(admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    status_counts = pipeline.db.zakupki.get_status_counts()
    total = sum(status_counts.values())
    return {
        "total_zakupki": total,
        "by_status": status_counts,
        "summary": {
            "ready_for_users": status_counts.get(ZakupkaStatus.URL_READY, 0),
            "needs_ai": status_counts.get(ZakupkaStatus.RAW, 0),
            "needs_links": status_counts.get(ZakupkaStatus.AI_READY, 0),
            "completed": status_counts.get(ZakupkaStatus.STAGE4_DONE, 0),
        },
    }


@router.get("/api/admin/zakupki_all")
def get_all_zakupki(
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    page, total = pipeline.db.zakupki.get_admin_all_page(offset=offset, limit=limit)
    result = []
    for z in page:
        result.append(
            {
                "reg_number": z.reg_number,
                "description": z.description,
                "update_date": z.update_date,
                "bid_end_date": z.bid_end_date,
                "initial_price": z.initial_price,
                "link": z.link,
                "status": z.status,
            }
        )
    return {"items": result, "total": total, "offset": offset, "limit": limit}


@router.post("/api/admin/batch_stage2")
def admin_batch_stage2(
    req: BatchStage2Request,
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    if req.limit:
        page_limit = int(req.limit)
        pending_zakupki, pending_total = pipeline.get_stage2_pending_page(offset=0, limit=page_limit)
        total_available = pending_total
    else:
        pending_zakupki = pipeline.get_stage2_pending_items(limit=None, offset=0)
        total_available = len(pending_zakupki)
    if total_available == 0 or not pending_zakupki:
        return {"status": "warning", "message": "Нет закупок для AI обработки"}

    reg_numbers = [z.reg_number for z in pending_zakupki]
    result = pipeline.run_stage2(reg_numbers=reg_numbers)
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "total_available": total_available,
        "errors": result.errors,
    }


@router.post("/api/admin/batch_stage3")
def admin_batch_stage3(
    req: BatchStage3Request,
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    ai_ready_zakupki = pipeline.db.zakupki.get_by_status(ZakupkaStatus.AI_READY)
    if not ai_ready_zakupki:
        return {"status": "warning", "message": "Нет закупок для генерации ссылок"}
    if req.limit:
        ai_ready_zakupki = ai_ready_zakupki[:req.limit]
    reg_numbers = [z.reg_number for z in ai_ready_zakupki]
    result = pipeline.run_stage3(reg_numbers=reg_numbers)
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "generated": result.data.get("generated", 0),
        "total_available": len(ai_ready_zakupki),
        "errors": result.errors,
    }
