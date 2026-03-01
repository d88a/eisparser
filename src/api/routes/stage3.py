"""Stage 3 routes."""

from fastapi import APIRouter, Depends

from .common import RunStage3Request, admin_required


router = APIRouter()


@router.post("/api/actions/run_stage3")
def run_stage3(req: RunStage3Request, admin: bool = Depends(admin_required)):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    if not req.reg_numbers:
        return {"status": "warning", "message": "reg_numbers is required"}
    result = pipeline.run_stage3(reg_numbers=req.reg_numbers, overwrite=req.overwrite)
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "generated": result.data.get("generated", 0),
        "items": result.data.get("items", []),
        "errors": result.errors,
    }


@router.get("/api/stage3")
def get_stage3_data(
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required),
):
    from ..app import get_pipeline

    pipeline = get_pipeline()
    rows, total = pipeline.db.ai_results.get_stage3_page(offset=offset, limit=limit)
    items = []
    for row in rows:
        items.append(
            {
                "reg_number": row.get("reg_number", ""),
                "description": row.get("description") or "",
                "update_date": row.get("update_date") or "",
                "bid_end_date": row.get("bid_end_date") or "",
                "initial_price": row.get("initial_price"),
                "link": row.get("link") or "",
                "two_gis_url": row.get("two_gis_url"),
                "processed_at": str(row.get("processed_at") or ""),
                "ai_city": row.get("ai_city"),
                "ai_area_min": row.get("ai_area_min"),
                "ai_area_max": row.get("ai_area_max"),
            }
        )

    return {"items": items, "total": total, "offset": offset, "limit": limit}
