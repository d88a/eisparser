"""Stage 4 routes."""

from fastapi import APIRouter, Depends

from models.statuses import STAGE4_PROCESSED_STATUSES, STAGE4_QUEUE_STATUSES, ZakupkaStatus

from .common import RunStage4Request, admin_required


router = APIRouter()


@router.get("/api/stage4")
def get_stage4_data(
    offset: int = 0,
    limit: int = 20,
    view: str = "queue",
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    stage4_statuses = STAGE4_PROCESSED_STATUSES if view == "processed" else STAGE4_QUEUE_STATUSES
    rows, total = pipeline.db.zakupki.get_stage4_page_with_ai_city(
        statuses=list(stage4_statuses),
        offset=offset,
        limit=limit,
        processed_view=(view == "processed"),
    )
    items = []
    for row in rows:
        items.append(
            {
                "reg_number": row.get("reg_number", ""),
                "description": row.get("description"),
                "update_date": row.get("update_date"),
                "bid_end_date": row.get("bid_end_date"),
                "initial_price": row.get("initial_price"),
                "link": row.get("link"),
                "two_gis_url": row.get("two_gis_url"),
                "status": row.get("status"),
                "ai_city": row.get("ai_city"),
            }
        )
    return {"items": items, "total": total, "offset": offset, "limit": limit, "view": view}


@router.get("/api/stage4/{reg_number}/listings")
def get_stage4_listings(reg_number: str, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    listings = pipeline.db.listings.get_for_zakupka(reg_number)
    items = []
    for i, listing in enumerate(listings, 1):
        d = listing.to_dict() if hasattr(listing, "to_dict") else dict(listing)
        items.append(
            {
                "rank": d.get("rank") if d.get("rank") is not None else i,
                "price_rub": d.get("price_rub"),
                "address": d.get("address"),
                "rooms": d.get("rooms"),
                "area_m2": d.get("area_m2"),
                "floor": d.get("floor"),
                "building_floors": d.get("building_floors"),
                "building_year": d.get("building_year"),
                "two_gis_url": d.get("two_gis_url"),
                "external_source": d.get("external_source"),
                "external_url": d.get("external_url"),
            }
        )
    return {"reg_number": reg_number, "items": items, "total": len(items)}


@router.post("/api/actions/run_stage4")
def run_stage4(req: RunStage4Request, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    if not req.reg_numbers:
        return {"status": "warning", "message": "reg_numbers is required"}

    zakupki_by_reg = {z.reg_number: z for z in pipeline.db.zakupki.get_by_reg_numbers(req.reg_numbers)}
    processed = 0
    total_listings = 0
    errors = []

    for reg_number in req.reg_numbers:
        z = zakupki_by_reg.get(reg_number)
        if not z:
            errors.append(f"{reg_number}: закупка не найдена")
            continue
        if z.status not in STAGE4_QUEUE_STATUSES:
            errors.append(
                f"{reg_number}: статус '{z.status}', ожидается '{ZakupkaStatus.URL_READY}' или '{ZakupkaStatus.STAGE4_ERROR}'"
            )
            continue
        if not z.two_gis_url:
            errors.append(f"{reg_number}: Ссылки нет (Этап 3)")
            continue
        try:
            result = pipeline.run_stage4_for_zakupka(
                reg_number=z.reg_number,
                url=z.two_gis_url,
                top_n=req.top_n,
                get_details=req.get_details,
            )
            if result.error:
                errors.append(f"{z.reg_number}: {result.error}")
            else:
                processed += 1
                total_listings += result.actual_n
            pipeline.logger.info(
                "stage_progress reg_number=%s stage=4 result=%s reason=%s",
                z.reg_number,
                "error" if result.error else "ok",
                result.error or f"listings={result.actual_n}",
            )
        except Exception as e:
            errors.append(f"{z.reg_number}: {e}")
            pipeline.db.zakupki.update_status(z.reg_number, ZakupkaStatus.STAGE4_ERROR)
            pipeline.logger.info(
                "stage_progress reg_number=%s stage=4 result=error reason=%s",
                z.reg_number,
                e,
            )

    return {
        "status": "ok" if processed > 0 and not errors else ("warning" if processed > 0 else "error"),
        "message": f"Собрано {total_listings} объявлений из {processed} закупок",
        "processed": processed,
        "total_listings": total_listings,
        "errors": errors,
    }
