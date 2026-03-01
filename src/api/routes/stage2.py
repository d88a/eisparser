"""Stage 1/2 and overrides routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from models.decision import Decision
from models.statuses import ZakupkaStatus
from models.user_override import UserOverride
from models.zakupka import Zakupka

from .common import (
    DecisionRequest,
    OverrideRequest,
    RunStage2Request,
    SaveStage1SelectedRequest,
    admin_required,
)


router = APIRouter()


@router.get("/api/stage1")
def get_stage1_data(user_id: int = 1, limit: int = 10, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    _ = user_id
    purchases = pipeline.eis_downloader.search_zakupki(limit=limit)
    result = []
    for p in purchases:
        update_date = p.get("update_date")
        update_str = update_date.isoformat() if hasattr(update_date, "isoformat") else str(update_date or "")
        result.append(
            {
                "reg_number": p.get("reg_number", ""),
                "description": p.get("description", ""),
                "update_date": update_str,
                "bid_end_date": p.get("bid_end_date", ""),
                "initial_price": p.get("initial_price"),
                "link": p.get("link", ""),
            }
        )
    return result


@router.post("/api/actions/save_stage1_selected")
def save_stage1_selected(req: SaveStage1SelectedRequest, admin: bool = Depends(admin_required)):
    import os
    import shutil

    from ..app import get_pipeline

    pipeline = get_pipeline()
    saved = 0
    skipped = 0
    errors = []

    for item in req.items:
        reg_number = item.reg_number
        try:
            existing = pipeline.eis.get_zakupka(reg_number)
            combined_text = existing.combined_text if existing and existing.combined_text else ""

            if not combined_text:
                combined_path = pipeline.eis_downloader.download_documents(reg_number)
                if combined_path and os.path.exists(combined_path):
                    with open(combined_path, "r", encoding="utf-8") as f:
                        combined_text = f.read()

            if not combined_text.strip():
                skipped += 1
                continue

            bid_end_date = (item.bid_end_date or "").strip()
            if not bid_end_date:
                bid_end_date = pipeline.eis_downloader.extract_bid_end_date(combined_text)
            initial_price = item.initial_price
            if initial_price is None:
                initial_price = pipeline.eis_downloader.extract_initial_price(combined_text)

            zakupka = Zakupka(
                reg_number=reg_number,
                description=item.description or "",
                update_date=item.update_date or "",
                bid_end_date=bid_end_date,
                initial_price=initial_price,
                link=item.link or "",
                combined_text=combined_text,
                status=ZakupkaStatus.RAW,
            )

            if pipeline.eis.save_zakupka(zakupka):
                saved += 1
                pipeline.db.zakupki.update_status(reg_number, ZakupkaStatus.RAW)

                decision = Decision(
                    user_id=req.user_id,
                    reg_number=reg_number,
                    stage=1,
                    decision="approved",
                    comment=None,
                )
                pipeline.db.decisions.save(decision)

                zakupka_dir = pipeline.eis_downloader.zakupki_dir / reg_number
                if zakupka_dir.exists():
                    shutil.rmtree(zakupka_dir, ignore_errors=True)
        except Exception as e:
            errors.append(f"{reg_number}: {e}")

    return {
        "status": "ok" if saved > 0 else "warning",
        "saved": saved,
        "skipped": skipped,
        "errors": errors,
        "message": f"Сохранено {saved} закупок, пропущено {skipped}",
    }


@router.post("/api/decisions")
def save_decision(decision_data: DecisionRequest, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()

    decision = Decision(
        user_id=decision_data.user_id,
        reg_number=decision_data.reg_number,
        stage=decision_data.stage,
        decision=decision_data.decision,
        comment=decision_data.comment,
    )

    success = pipeline.db.decisions.save(decision)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save decision")

    return {"status": "ok", "decision": decision.decision}


@router.post("/api/actions/run_stage2")
def run_stage2(req: RunStage2Request, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()

    target_ids = []
    if req.reg_numbers:
        if req.overwrite:
            target_ids = list(req.reg_numbers)
        else:
            selected = pipeline.eis.get_by_reg_numbers(req.reg_numbers)
            for z in selected:
                ai_result = pipeline.ai.get_result(z.reg_number)
                eligible, _ = pipeline.get_stage2_eligibility_reason(z, ai_result, overwrite=False)
                if eligible:
                    target_ids.append(z.reg_number)
    else:
        pending_items = pipeline.get_stage2_pending_items(limit=None, offset=0)
        target_ids = [z.reg_number for z in pending_items]

    if not target_ids:
        return {"status": "warning", "message": "Нет закупок, ожидающих Stage 2"}

    result = pipeline.run_stage2(reg_numbers=target_ids, overwrite=req.overwrite)
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "processed_reg_numbers": result.data.get("processed_reg_numbers", []),
        "failed_reg_numbers": result.data.get("failed_reg_numbers", []),
        "errors": result.errors,
    }


@router.get("/api/stage2")
def get_stage2_data(
    user_id: int = 1,
    offset: int = 0,
    limit: int = 20,
    view: str = "pending",
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    _ = user_id

    page = []
    if view in ("processed", "recent"):
        rows, total = pipeline.db.zakupki.get_stage2_processed_page(offset=offset, limit=limit)
        for row in rows:
            page.append(
                {
                    "reg_number": row.get("reg_number", ""),
                    "description": row.get("description") or "",
                    "update_date": row.get("update_date") or "",
                    "bid_end_date": row.get("bid_end_date") or "",
                    "initial_price": row.get("initial_price"),
                    "processed_at": str(row.get("processed_at") or ""),
                    "combined_text": "",
                    "status": row.get("status"),
                    "ai_city": row.get("ai_city"),
                    "ai_area_min": row.get("ai_area_min"),
                    "ai_area_max": row.get("ai_area_max"),
                    "ai_zakupka_name": row.get("ai_zakupka_name"),
                    "ai_address": row.get("ai_address"),
                    "ai_rooms": row.get("ai_rooms"),
                    "ai_floor": row.get("ai_floor"),
                    "ai_building_floors_min": row.get("ai_building_floors_min"),
                    "ai_year_build": row.get("ai_year_build"),
                    "ai_wear_percent": row.get("ai_wear_percent"),
                    "ai_zakazchik": row.get("ai_zakazchik"),
                }
            )
    else:
        page_items, total = pipeline.get_stage2_pending_page(offset=offset, limit=limit)
        for z in page_items:
            page.append(
                {
                    "reg_number": z.reg_number,
                    "description": z.description or "",
                    "update_date": z.update_date or "",
                    "bid_end_date": z.bid_end_date or "",
                    "initial_price": z.initial_price,
                    "processed_at": z.processed_at.isoformat() if z.processed_at else None,
                    "combined_text": "",
                    "status": z.status,
                    "ai_city": None,
                    "ai_area_min": None,
                    "ai_area_max": None,
                    "ai_zakupka_name": None,
                    "ai_address": None,
                    "ai_rooms": None,
                    "ai_floor": None,
                    "ai_building_floors_min": None,
                    "ai_year_build": None,
                    "ai_wear_percent": None,
                    "ai_zakazchik": None,
                }
            )

    return {"items": page, "total": total, "offset": offset, "limit": limit, "view": view}


@router.get("/api/stage2/{reg_number}")
def get_stage2_item(reg_number: str, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    z = pipeline.db.zakupki.get_by_id(reg_number)
    if not z:
        raise HTTPException(status_code=404, detail="Purchase not found")

    ai = pipeline.db.ai_results.get_by_id(reg_number)
    return {
        "reg_number": z.reg_number,
        "description": z.description or "",
        "update_date": z.update_date or "",
        "bid_end_date": z.bid_end_date or "",
        "initial_price": z.initial_price,
        "processed_at": z.processed_at.isoformat() if isinstance(z.processed_at, datetime) else str(z.processed_at or ""),
        "combined_text": z.combined_text or "",
        "status": z.status,
        "ai_city": ai.city if ai else None,
        "ai_area_min": ai.area_min_m2 if ai else None,
        "ai_area_max": ai.area_max_m2 if ai else None,
        "ai_zakupka_name": ai.zakupka_name if ai else None,
        "ai_address": ai.address if ai else None,
        "ai_rooms": ai.rooms if ai else None,
        "ai_floor": ai.floor if ai else None,
        "ai_building_floors_min": ai.building_floors_min if ai else None,
        "ai_year_build": ai.year_build_str if ai else None,
        "ai_wear_percent": ai.wear_percent if ai else None,
        "ai_zakazchik": ai.zakazchik if ai else None,
    }


@router.post("/api/overrides")
def save_override(req: OverrideRequest, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    override = UserOverride(
        user_id=req.user_id,
        reg_number=req.reg_number,
        field_name=req.field_name,
        value=req.value,
    )
    if pipeline.db.user_overrides.save(override):
        return {"status": "ok", "message": f"Сохранено: {req.field_name} = {req.value}"}
    return {"status": "error", "message": "Не удалось сохранить"}


@router.get("/api/overrides/{reg_number}")
def get_overrides(reg_number: str, user_id: int = 1, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    return pipeline.db.user_overrides.get_for_zakupka(reg_number, user_id)
