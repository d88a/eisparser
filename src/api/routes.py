"""
API Р РѕСѓС‚С‹ РґР»СЏ UI.
"""
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, Body, Depends, Response, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config.settings import settings
from services.view_service import ViewService
from models.decision import Decision
from models.zakupka import Zakupka
from models.user_override import UserOverride

router = APIRouter()

# РЁР°Р±Р»РѕРЅС‹
base_dir = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(base_dir / "web" / "templates"))

# ==========================================
# Pydantic Models
# ==========================================

class DecisionRequest(BaseModel):
    user_id: int
    reg_number: str
    stage: int
    decision: str
    comment: Optional[str] = None

class RunStage2Request(BaseModel):
    user_id: int
    reg_numbers: Optional[List[str]] = None
    overwrite: bool = False

class RunStage3Request(BaseModel):
    reg_numbers: Optional[List[str]] = None
    overwrite: bool = False

class RunStage4Request(BaseModel):
    reg_numbers: List[str]
    top_n: int = Field(default=20, ge=1, le=200)
    get_details: bool = False

class Stage1PurchaseItem(BaseModel):
    reg_number: str
    description: Optional[str] = ""
    update_date: Optional[str] = ""
    bid_end_date: Optional[str] = ""
    initial_price: Optional[float] = None
    link: Optional[str] = ""

class SaveStage1SelectedRequest(BaseModel):
    user_id: int
    items: List[Stage1PurchaseItem]

class OverrideRequest(BaseModel):
    user_id: int
    reg_number: str
    field_name: str
    value: str

# Stage 2 / User Flow Models
class UserSelectRequest(BaseModel):
    user_id: int
    reg_numbers: List[str]

class UserUnselectRequest(BaseModel):
    user_id: int
    reg_numbers: List[str]

class UserRunStage4Request(BaseModel):
    user_id: int
    top_n: int = Field(default=20, ge=1, le=200)
    get_details: bool = False

# Admin Batch Models
class BatchStage2Request(BaseModel):
    limit: Optional[int] = None

class BatchStage3Request(BaseModel):
    limit: Optional[int] = None


# ==========================================
# AUTH & SECURITY
# ==========================================

def get_current_admin(request: Request):
    """Dependency to check if user is admin."""
    token = request.cookies.get("admin_token")
    if token != settings.admin_password:
        return None
    return True

def admin_required(admin: bool = Depends(get_current_admin)):
    """Dependency that raises error if not admin."""
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin access required"
        )
    return True

# ==========================================
# VIEW ROUTES (HTML)
# ==========================================

@router.get("/admin/login")
def login_page(request: Request):
    """РЎС‚СЂР°РЅРёС†Р° РІС…РѕРґР° РґР»СЏ Р°РґРјРёРЅР°."""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/admin/login")
async def login_submit(request: Request):
    """РћР±СЂР°Р±РѕС‚РєР° РІС…РѕРґР°."""
    from urllib.parse import parse_qs
    body = await request.body()
    password = None
    if body:
        data = parse_qs(body.decode("utf-8"))
        password = data.get("password", [None])[0]
    
    if password == settings.admin_password:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="admin_token", value=password, httponly=True, path="/")
        return response
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Неверный пароль"
    })

@router.get("/admin/logout")
def logout():
    """Р’С‹С…РѕРґ."""
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie("admin_token")
    return response

@router.get("/")
def read_root(request: Request, admin: Optional[bool] = Depends(get_current_admin)):
    """Р“Р»Р°РІРЅР°СЏ СЃС‚СЂР°РЅРёС†Р° (Dashboard). Р•СЃР»Рё РЅРµ Р°РґРјРёРЅ вЂ” СЂРµРґРёСЂРµРєС‚ РЅР° РІС‹Р±РѕСЂ."""
    if admin:
        return templates.TemplateResponse("index.html", {"request": request, "is_admin": True})
    return templates.TemplateResponse("landing.html", {"request": request})

@router.get("/stage2")
def read_stage2(request: Request, admin: bool = Depends(admin_required)):
    """РЎС‚СЂР°РЅРёС†Р° Stage 2 (С‚РѕР»СЊРєРѕ Р°РґРјРёРЅ)."""
    return templates.TemplateResponse("stage2.html", {"request": request, "is_admin": True})

@router.get("/stage3")
def read_stage3(request: Request, admin: bool = Depends(admin_required)):
    """РЎС‚СЂР°РЅРёС†Р° Stage 3 (С‚РѕР»СЊРєРѕ Р°РґРјРёРЅ)."""
    return templates.TemplateResponse("stage3.html", {"request": request, "is_admin": True})



@router.get("/stage4")
def read_stage4(request: Request, admin: bool = Depends(admin_required)):
    """Stage 4 page (admin only)."""
    return templates.TemplateResponse("stage4.html", {"request": request, "is_admin": True})


@router.get("/user/available")
def read_user_available(request: Request, admin: bool = Depends(admin_required)):
    """User available page (admin only)."""
    return templates.TemplateResponse("user_available.html", {"request": request, "is_admin": True})


@router.get("/user/selections")
def read_user_selections(request: Request, admin: Optional[bool] = Depends(get_current_admin)):
    """User selections page."""
    return templates.TemplateResponse("user_selections.html", {"request": request, "is_admin": bool(admin)})


@router.get("/api/stage1")
def get_stage1_data(user_id: int = 1, limit: int = 10, admin: bool = Depends(admin_required)):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ Р±С‹СЃС‚СЂС‹Р№ СЃРїРёСЃРѕРє Р·Р°РєСѓРїРѕРє СЃ Р•РРЎ (Р±РµР· СЃРѕС…СЂР°РЅРµРЅРёСЏ РІ Р‘Р”)."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    purchases = pipeline.eis_downloader.search_zakupki(limit=limit)
    result = []
    for p in purchases:
        update_date = p.get("update_date")
        update_str = update_date.isoformat() if hasattr(update_date, "isoformat") else str(update_date or "")
        result.append({
            "reg_number": p.get("reg_number", ""),
            "description": p.get("description", ""),
            "update_date": update_str,
            "bid_end_date": p.get("bid_end_date", ""),
            "initial_price": p.get("initial_price"),
            "link": p.get("link", ""),
        })
    return result


@router.post("/api/actions/save_stage1_selected")
def save_stage1_selected(req: SaveStage1SelectedRequest, admin: bool = Depends(admin_required)):
    """РЎРєР°С‡РёРІР°РµС‚ РґРѕРєСѓРјРµРЅС‚С‹ Рё СЃРѕС…СЂР°РЅСЏРµС‚ РІ Р‘Р” С‚РѕР»СЊРєРѕ РІС‹Р±СЂР°РЅРЅС‹Рµ Р·Р°РєСѓРїРєРё (Р­С‚Р°Рї 1)."""
    import os
    import shutil
    from .app import get_pipeline
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
                    with open(combined_path, 'r', encoding='utf-8') as f:
                        combined_text = f.read()

            if not combined_text.strip():
                skipped += 1
                continue

            bid_end_date = (item.bid_end_date or "").strip()
            if not bid_end_date:
                bid_end_date = pipeline.eis_downloader._extract_bid_end_date_from_text(combined_text)
            initial_price = item.initial_price
            if initial_price is None:
                initial_price = pipeline.eis_downloader._extract_initial_price_from_text(combined_text)

            zakupka = Zakupka(
                reg_number=reg_number,
                description=item.description or "",
                update_date=item.update_date or "",
                bid_end_date=bid_end_date,
                initial_price=initial_price,
                link=item.link or "",
                combined_text=combined_text,
                status='raw'
            )

            if pipeline.eis.save_zakupka(zakupka):
                saved += 1
                pipeline.db.zakupki.update_status(reg_number, 'raw')

                decision = Decision(
                    user_id=req.user_id,
                    reg_number=reg_number,
                    stage=1,
                    decision='approved',
                    comment=None
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
        "message": f"Сохранено {saved} закупок, пропущено {skipped}"
    }


@router.post("/api/decisions")
def save_decision(decision_data: DecisionRequest, admin: bool = Depends(admin_required)):
    """РЎРѕС…СЂР°РЅСЏРµС‚ СЂРµС€РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (С‚РѕР»СЊРєРѕ РґР»СЏ Р°РґРјРёРЅР°)."""
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


@router.post("/api/actions/run_stage2")
def run_stage2(req: RunStage2Request, admin: bool = Depends(admin_required)):
    """Р—Р°РїСѓСЃРєР°РµС‚ РР-Р°РЅР°Р»РёР· РґР»СЏ РІС‹Р±СЂР°РЅРЅС‹С… Р·Р°РєСѓРїРѕРє (СЃ РѕРїС†РёРѕРЅР°Р»СЊРЅРѕР№ РїРµСЂРµР·Р°РїРёСЃСЊСЋ)."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    pending_reg_numbers = {z.reg_number for z in pipeline.get_stage2_pending_items()}
    target_ids = list(pending_reg_numbers)
    if req.reg_numbers:
        target_ids = [r for r in req.reg_numbers if r in pending_reg_numbers]

    if not target_ids:
        return {"status": "warning", "message": "Нет закупок, ожидающих Stage 2"}

    result = pipeline.run_stage2(reg_numbers=target_ids, overwrite=req.overwrite)

    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "errors": result.errors
    }

@router.get("/api/stage2")
def get_stage2_data(
    user_id: int = 1,
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required)
):
    """РџРѕР»СѓС‡Р°РµС‚ РґР°РЅРЅС‹Рµ РґР»СЏ РїСЂРѕРІРµСЂРєРё AI (Stage 2) СЃ РїР°РіРёРЅР°С†РёРµР№."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    items = ViewService(pipeline.db).get_zakupka_stage_view(user_id, 2)
    items.sort(key=lambda x: (x.processed_at or x.update_date or ""), reverse=True)
    total = len(items)
    page = items[offset: offset + limit]

    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.post("/api/actions/run_stage3")
def run_stage3(req: RunStage3Request, admin: bool = Depends(admin_required)):
    """Run Stage 3 link generation for selected items."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    if not req.reg_numbers:
        return {"status": "warning", "message": "reg_numbers is required"}

    result = pipeline.run_stage3(reg_numbers=req.reg_numbers, overwrite=req.overwrite)

    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "generated": result.data.get("generated", 0),
        "items": result.data.get("items", []),
        "errors": result.errors
    }


@router.get("/api/stage3")
def get_stage3_data(
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required)
):
    """Return AI-processed purchases for Stage 3."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    ai_results = pipeline.db.ai_results.get_all()
    reg_numbers = [r.reg_number for r in ai_results]
    zakupki = {z.reg_number: z for z in pipeline.db.zakupki.get_by_reg_numbers(reg_numbers)}

    items = []
    for ai in ai_results:
        z = zakupki.get(ai.reg_number)
        items.append({
            "reg_number": ai.reg_number,
            "description": z.description if z else "",
            "update_date": z.update_date if z else "",
            "bid_end_date": z.bid_end_date if z else "",
            "initial_price": z.initial_price if z else None,
            "link": z.link if z else "",
            "two_gis_url": z.two_gis_url if z else None,
            "processed_at": z.processed_at.isoformat() if z and z.processed_at else None,
            "ai_city": ai.city,
            "ai_area_min": ai.area_min_m2,
            "ai_area_max": ai.area_max_m2,
        })

    items.sort(key=lambda x: (x.get("processed_at") or x.get("update_date") or ""), reverse=True)
    total = len(items)
    page = items[offset: offset + limit]

    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/api/stage4")
def get_stage4_data(
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required)
):
    """Return purchases visible on Stage 4 page."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    # Keep processed purchases in the same queue so operator can re-open results
    # after run_stage4 without switching pages.
    stage4_statuses = ("url_ready", "listings_fresh", "listings_stale")
    by_reg = {}
    for status_name in stage4_statuses:
        for z in pipeline.db.zakupki.get_by_status(status_name):
            by_reg[z.reg_number] = z

    zakupki = list(by_reg.values())
    zakupki = sorted(
        zakupki,
        key=lambda z: (
            str(z.processed_at) if z.processed_at else (
                str(z.prepared_at) if z.prepared_at else z.update_date or ""
            )
        ),
        reverse=True
    )

    total = len(zakupki)
    page = zakupki[offset: offset + limit]

    items = []
    for z in page:
        ai = pipeline.ai.get_result(z.reg_number)
        items.append({
            "reg_number": z.reg_number,
            "description": z.description,
            "update_date": z.update_date,
            "bid_end_date": z.bid_end_date,
            "initial_price": z.initial_price,
            "link": z.link,
            "two_gis_url": z.two_gis_url,
            "status": z.status,
            "ai_city": ai.city if ai else None
        })

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/api/stage4/{reg_number}/listings")
def get_stage4_listings(reg_number: str, admin: bool = Depends(admin_required)):
    """Return collected listings for one purchase."""
    from .app import get_pipeline
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
    """Run Stage 4 for selected purchases."""
    from .app import get_pipeline
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
            errors.append(f"{reg_number}: \u0437\u0430\u043a\u0443\u043f\u043a\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430")
            continue
        if z.status not in ("url_ready", "listings_fresh", "listings_stale"):
            errors.append(f"{reg_number}: \u0441\u0442\u0430\u0442\u0443\u0441 '{z.status}', \u043e\u0436\u0438\u0434\u0430\u0435\u0442\u0441\u044f 'url_ready', 'listings_fresh' \u0438\u043b\u0438 'listings_stale'")
            continue
        if not z.two_gis_url:
            errors.append(f"{reg_number}: \u0421\u0441\u044b\u043b\u043a\u0438 \u043d\u0435\u0442 (\u042d\u0442\u0430\u043f 3)")
            continue

        try:
            result = pipeline.run_stage4_for_zakupka(
                reg_number=z.reg_number,
                url=z.two_gis_url,
                top_n=req.top_n,
                get_details=req.get_details
            )
            processed += 1
            total_listings += result.actual_n
            if result.error:
                errors.append(f"{z.reg_number}: {result.error}")
        except Exception as e:
            errors.append(f"{z.reg_number}: {e}")

    return {
        "status": "ok" if processed > 0 else "error",
        "message": f"\u0421\u043e\u0431\u0440\u0430\u043d\u043e {total_listings} \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u0438\u0437 {processed} \u0437\u0430\u043a\u0443\u043f\u043e\u043a",
        "processed": processed,
        "total_listings": total_listings,
        "errors": errors
    }



# ==========================================
# OVERRIDES API
# ==========================================

@router.post("/api/overrides")
def save_override(req: OverrideRequest, admin: bool = Depends(admin_required)):
    """РЎРѕС…СЂР°РЅСЏРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊСЃРєРѕРµ РїРµСЂРµРѕРїСЂРµРґРµР»РµРЅРёРµ AI-РїРѕР»СЏ."""
    from .app import get_pipeline
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
def get_overrides(reg_number: str, user_id: int = 1, admin: bool = Depends(admin_required)):
    """РџРѕР»СѓС‡Р°РµС‚ РІСЃРµ overrides РґР»СЏ Р·Р°РєСѓРїРєРё."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    return pipeline.db.user_overrides.get_for_zakupka(reg_number, user_id)


# ==========================================
# USER API (Stage 2 Integration)
# ==========================================

@router.get("/api/user/available_zakupki")
def get_available_zakupki(user_id: int = 1, offset: int = 0, limit: int = 10):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ Р·Р°РєСѓРїРєРё СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј 'url_ready' (РіРѕС‚РѕРІС‹Рµ Рє Р°РЅР°Р»РёР·Сѓ)."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    # РСЃРїСЂР°РІР»РµРЅРѕ: pipeline.db_service -> pipeline.db
    # РЎРЅР°С‡Р°Р»Р° РїРѕР»СѓС‡Р°РµРј РІСЃРµ (РѕРїС‚РёРјРёР·Р°С†РёСЏ: Р»СѓС‡С€Рµ Р±С‹ РІ СЂРµРїРѕ РґРѕР±Р°РІРёС‚СЊ limit/offset)
    all_zakupki = pipeline.db.zakupki.get_by_status('url_ready')
    
    # РЎРѕСЂС‚РёСЂРѕРІРєР° РїРѕ СЃРІРµР¶РµСЃС‚Рё (РµСЃР»Рё РµСЃС‚СЊ update_date РёР»Рё РїСЂРѕСЃС‚Рѕ desc)
    # РџСЂРµРґРїРѕР»РѕР¶РёРј, С‡С‚Рѕ Р±Р°Р·Р° РІРѕР·РІСЂР°С‰Р°РµС‚ РєР°Рє РµСЃС‚СЊ.
    
    # РџР°РіРёРЅР°С†РёСЏ in-memory (РґР»СЏ MVP РїРѕР№РґРµС‚, РЅРѕ Р»СѓС‡С€Рµ РІ SQL)
    zakupki = all_zakupki[offset : offset + limit]
    
    selected_reg_numbers = set(pipeline.db.user_selections.get_user_selections(user_id))
    
    result = []
    for z in zakupki:
        # РСЃРїСЂР°РІР»РµРЅРѕ: РёСЃРїРѕР»СЊР·СѓРµРј СЃРµСЂРІРёСЃ РІРјРµСЃС‚Рѕ РїСЂСЏРјРѕРіРѕ РґРѕСЃС‚СѓРїР° Рє СЂРµРїРѕ
        ai_result = pipeline.ai.get_result(z.reg_number)
        
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
    
    return {
        "zakupki": result, 
        "total": len(all_zakupki),
        "offset": offset,
        "limit": limit
    }


@router.post("/api/user/select")
def user_select(req: UserSelectRequest):
    """Р”РѕР±Р°РІР»СЏРµС‚ Р·Р°РєСѓРїРєРё РІ РІС‹Р±РѕСЂРєСѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    from .app import get_pipeline
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
        "message": f"Добавлено {added} закупок в выборку"
    }


@router.post("/api/user/unselect")
def user_unselect(req: UserUnselectRequest):
    """РЈРґР°Р»СЏРµС‚ Р·Р°РєСѓРїРєРё РёР· РІС‹Р±РѕСЂРєРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    from .app import get_pipeline
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
        "message": f"Удалено {removed} закупок из выборки"
    }


@router.get("/api/user/selections")
def get_user_selections(user_id: int = 1):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє РІС‹Р±СЂР°РЅРЅС‹С… Р·Р°РєСѓРїРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    reg_numbers = pipeline.db.user_selections.get_user_selections(user_id)
    
    if not reg_numbers:
        return {"zakupki": [], "total": 0}
    
    zakupki = pipeline.db.zakupki.get_by_reg_numbers(reg_numbers)
    
    result = []
    for z in zakupki:
        ai_result = pipeline.ai.get_result(z.reg_number)
        
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
    """Р—Р°РїСѓСЃРєР°РµС‚ Stage 4 (СЃР±РѕСЂ РѕР±СЉСЏРІР»РµРЅРёР№) РґР»СЏ РІС‹Р±СЂР°РЅРЅС‹С… Р·Р°РєСѓРїРѕРє РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    reg_numbers = pipeline.db.user_selections.get_user_selections(req.user_id)
    
    if not reg_numbers:
        return {"status": "warning", "message": "Нет выбранных закупок"}
    
    zakupki = pipeline.db.zakupki.get_by_reg_numbers(reg_numbers)
    # Р¤РёР»СЊС‚СЂСѓРµРј С‚РѕР»СЊРєРѕ С‚Рµ, Сѓ РєРѕС‚РѕСЂС‹С… РµСЃС‚СЊ URL Рё РїСЂР°РІРёР»СЊРЅС‹Р№ СЃС‚Р°С‚СѓСЃ (Gate Stage 4)
    zakupki_with_url = [z for z in zakupki if z.two_gis_url and z.status == 'url_ready']
    
    if not zakupki_with_url:
        return {"status": "warning", "message": "\u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0435\u0442 \u0438\u043b\u0438 \u0437\u0430\u043a\u0443\u043f\u043a\u0438 \u0435\u0449\u0435 \u043d\u0435 \u0433\u043e\u0442\u043e\u0432\u044b \u043a Stage 4"}
    
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
    
    if processed > 0:
        pipeline.db.user_selections.clear_user_selections(req.user_id)
    
    return {
        "status": "ok" if processed > 0 else "error",
        "processed": processed,
        "total_listings": total_listings,
        "message": f"\u0421\u043e\u0431\u0440\u0430\u043d\u043e {total_listings} \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u0438\u0437 {processed} \u0437\u0430\u043a\u0443\u043f\u043e\u043a",
        "errors": errors
    }


# ==========================================
# ADMIN API
# ==========================================

@router.post("/api/admin/cleanup_selected")
def cleanup_selected(admin: bool = Depends(admin_required)):
    """РЈРґР°Р»СЏРµС‚ РІСЃРµ СЂРµС€РµРЅРёСЏ СЃРѕ Р·РЅР°С‡РµРЅРёРµРј 'selected'."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    removed = pipeline.db.decisions.delete_by_decision_value("selected")
    return {"status": "ok", "removed": removed}

@router.get("/api/admin/pipeline_status")
def get_pipeline_status(admin: bool = Depends(admin_required)):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РїРѕ СЃС‚Р°С‚СѓСЃР°Рј Р·Р°РєСѓРїРѕРє."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    status_counts = pipeline.db.zakupki.get_status_counts()
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


@router.get("/api/admin/zakupki_all")
def get_all_zakupki(
    offset: int = 0,
    limit: int = 20,
    admin: bool = Depends(admin_required)
):
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ РІСЃРµ Р·Р°РєСѓРїРєРё РёР· Р‘Р” РґР»СЏ РІРєР»Р°РґРєРё 'Р’СЃРµ Р·Р°РєСѓРїРєРё' СЃ РїР°РіРёРЅР°С†РёРµР№."""
    from .app import get_pipeline
    pipeline = get_pipeline()

    zakupki = pipeline.db.zakupki.get_all()
    zakupki = sorted(
        zakupki,
        key=lambda z: (str(z.processed_at) if z.processed_at else z.update_date or ""),
        reverse=True
    )

    total = len(zakupki)
    page = zakupki[offset: offset + limit]

    result = []
    for z in page:
        result.append({
            "reg_number": z.reg_number,
            "description": z.description,
            "update_date": z.update_date,
            "bid_end_date": z.bid_end_date,
            "initial_price": z.initial_price,
            "link": z.link,
            "status": z.status
        })
    return {
        "items": result,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.post("/api/admin/batch_stage2")
def admin_batch_stage2(req: BatchStage2Request, admin: bool = Depends(admin_required)):
    """Массовая AI-обработка для закупок, ожидающих Stage 2."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    pending_zakupki = pipeline.get_stage2_pending_items()
    
    if not pending_zakupki:
        return {"status": "warning", "message": "Нет закупок для AI обработки"}
    
    if req.limit:
        pending_zakupki = pending_zakupki[:req.limit]
    
    reg_numbers = [z.reg_number for z in pending_zakupki]
    result = pipeline.run_stage2(reg_numbers=reg_numbers)
    
    return {
        "status": "ok" if result.success else "error",
        "message": result.message,
        "processed": result.data.get("processed", 0),
        "total_available": len(pending_zakupki),
        "errors": result.errors
    }


@router.post("/api/admin/batch_stage3")
def admin_batch_stage3(req: BatchStage3Request, admin: bool = Depends(admin_required)):
    """РњР°СЃСЃРѕРІР°СЏ РіРµРЅРµСЂР°С†РёСЏ СЃСЃС‹Р»РѕРє РґР»СЏ Р·Р°РєСѓРїРѕРє СЃРѕ СЃС‚Р°С‚СѓСЃРѕРј 'ai_ready'."""
    from .app import get_pipeline
    pipeline = get_pipeline()
    
    ai_ready_zakupki = pipeline.db.zakupki.get_by_status('ai_ready')
    
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
        "errors": result.errors
    }


