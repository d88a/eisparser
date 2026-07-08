from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from config.settings import settings
from models.statuses import STAGE4_QUEUE_STATUSES, ZakupkaStatus
from services.view_service import ViewService

from .common import (
    ReserveCheapestRequest,
    UserRunStage4Request,
    UserSelectRequest,
    UserUnselectRequest,
    get_current_public_user,
    public_api_auth_required,
    templates,
    user_access_required,
)


router = APIRouter()


class PublicProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)


class PublicPasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
    confirm_password: str


def _public_profile_from_email(email: str | None) -> dict:
    safe_email = (email or "").strip().lower()
    default_name = safe_email.split("@", 1)[0] if safe_email else ""
    display_name = default_name

    if safe_email:
        try:
            _, pipeline = _view_service()
            user = pipeline.db.users.get_by_email(safe_email) if hasattr(pipeline.db, "users") else None
            if user and getattr(user, "display_name", None):
                display_name = str(user.display_name).strip() or display_name
        except Exception:
            pass

    initials = "".join([x[0] for x in display_name.split() if x][:2]).upper() if display_name else "U"
    return {"display_name": display_name or safe_email or "Пользователь", "email": safe_email or None, "initials": initials}


def _view_service() -> tuple[ViewService, object]:
    from ..app import get_pipeline

    pipeline = get_pipeline()
    return ViewService(pipeline.db), pipeline


def _public_context(request: Request, current_user: dict | None) -> dict:
    profile = _public_profile_from_email((current_user or {}).get("email")) if current_user else None
    return {
        "request": request,
        "is_public_authenticated": bool(current_user),
        "public_user_email": (current_user or {}).get("email"),
        "public_profile": profile,
    }


def _public_login_redirect(next_path: str):
    safe_next = next_path if str(next_path or "").startswith("/") else "/public/zakupki"
    return RedirectResponse(
        url=f"/public/login?next={quote(safe_next, safe='/%?=&')}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/public/zakupki")
def public_zakupki_page(request: Request, current_user: dict | None = Depends(get_current_public_user)):
    return templates.TemplateResponse(request, "public_zakupki_list.html", _public_context(request, current_user))


@router.get("/public/reservations")
def public_reservations_page(
    request: Request,
    current_user: dict | None = Depends(get_current_public_user),
):
    if not current_user:
        return _public_login_redirect("/public/reservations")
    return templates.TemplateResponse(request, "public_reservations.html", _public_context(request, current_user))


@router.get("/public/account")
def public_account_page(
    request: Request,
    current_user: dict | None = Depends(get_current_public_user),
):
    if not current_user:
        return _public_login_redirect("/public/account")
    return templates.TemplateResponse(request, "public_account.html", _public_context(request, current_user))


@router.get("/public/zakupki/{reg_number}")
def public_zakupka_detail_page(
    reg_number: str,
    request: Request,
    current_user: dict | None = Depends(get_current_public_user),
):
    service, _ = _view_service()
    detail = service.get_public_zakupka_detail(
        reg_number,
        current_user_email=(current_user or {}).get("email"),
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Zakupka not found")
    return templates.TemplateResponse(
        request,
        "public_zakupka_detail.html",
        {**_public_context(request, current_user), "reg_number": reg_number},
    )


@router.get("/api/public/zakupki")
def get_public_zakupki(
    offset: int = 0,
    limit: int = 20,
    include_reserved: int = 0,
    current_user: dict | None = Depends(get_current_public_user),
):
    service, _ = _view_service()
    items, total = service.get_public_zakupki_page(
        offset=offset,
        limit=limit,
        include_reserved=bool(include_reserved),
        current_user_email=(current_user or {}).get("email"),
    )
    return {"items": items, "total": total, "offset": max(0, int(offset or 0)), "limit": max(1, int(limit or 20))}


@router.get("/api/public/reservations")
def get_public_reservations(
    tab: str = "active",
    status_filter: str = "all",
    sort_mode: str = "bid_end_asc",
    offset: int = 0,
    limit: int = 20,
    current_user: dict = Depends(public_api_auth_required),
):
    service, _ = _view_service()
    items, total = service.get_public_reservations_page(
        offset=offset,
        limit=limit,
        reserved_by=current_user["email"],
        tab=tab,
        status_filter=status_filter,
        sort_mode=sort_mode,
    )
    return {
        "items": items,
        "total": total,
        "offset": max(0, int(offset or 0)),
        "limit": max(1, int(limit or 20)),
        "tab": (tab or "active").strip().lower(),
        "status_filter": (status_filter or "all").strip().lower(),
        "sort_mode": (sort_mode or "bid_end_asc").strip().lower(),
    }


@router.get("/api/public/favorites")
def get_public_favorites(
    offset: int = 0,
    limit: int = 20,
    current_user: dict = Depends(public_api_auth_required),
):
    service, _ = _view_service()
    items, total = service.get_public_favorites_page(
        user_email=current_user["email"],
        offset=offset,
        limit=limit,
    )
    return {"items": items, "total": total, "offset": max(0, int(offset or 0)), "limit": max(1, int(limit or 20))}


@router.get("/api/public/account")
def get_public_account(
    current_user: dict = Depends(public_api_auth_required),
):
    _, pipeline = _view_service()
    user = pipeline.db.users.get_by_email(current_user["email"]) if hasattr(pipeline.db, "users") else None
    display_name = ""
    email = current_user["email"]
    if user:
        display_name = str(getattr(user, "display_name", "") or "").strip()
        email = str(getattr(user, "email", email) or email).strip().lower()
    if not display_name:
        display_name = email.split("@", 1)[0]
    return {"display_name": display_name, "email": email, "tariff_label": "Тариф: стандартный"}


@router.post("/api/public/account/profile")
def update_public_account_profile(
    req: PublicProfileUpdateRequest,
    current_user: dict = Depends(public_api_auth_required),
):
    _, pipeline = _view_service()
    display_name = " ".join((req.display_name or "").strip().split())
    if len(display_name) < 2 or len(display_name) > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid display_name length")
    if not hasattr(pipeline.db, "users"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Users unavailable")
    ok = pipeline.db.users.update_display_name(current_user["email"], display_name)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"status": "ok", "display_name": display_name}


@router.post("/api/public/account/password")
def update_public_account_password(
    req: PublicPasswordUpdateRequest,
    current_user: dict = Depends(public_api_auth_required),
):
    from .common import hash_public_password, verify_public_password

    _, pipeline = _view_service()
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password confirmation does not match")
    if len(req.new_password or "") < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password too short")
    if not hasattr(pipeline.db, "users"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Users unavailable")
    user = pipeline.db.users.get_by_email(current_user["email"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_public_password(req.current_password, getattr(user, "password_hash", None)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is incorrect")
    ok = pipeline.db.users.update_password_hash(current_user["email"], hash_public_password(req.new_password))
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")
    return {"status": "ok"}


@router.get("/api/public/zakupki/{reg_number}")
def get_public_zakupka(
    reg_number: str,
    current_user: dict | None = Depends(get_current_public_user),
):
    service, _ = _view_service()
    detail = service.get_public_zakupka_detail(
        reg_number,
        current_user_email=(current_user or {}).get("email"),
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Zakupka not found")
    return detail


@router.post("/api/public/zakupki/{reg_number}/reserve-cheapest")
def reserve_cheapest_listing(reg_number: str, req: ReserveCheapestRequest):
    # Deprecated: kept for backward compatibility. New public flow uses /reserve.
    reg = (reg_number or "").strip()
    if not reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")

    _, pipeline = _view_service()
    reservation = pipeline.db.listing_reservations.reserve_cheapest_available(
        reg_number=reg,
        reserved_by=(req.reserved_by or "anon"),
        ttl_hours=settings.reservation_ttl_hours,
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нет доступных вариантов для брони",
        )

    return {
        "status": "ok",
        "listing_id": reservation["listing_id"],
        "expires_at": reservation["expires_at"],
    }


@router.post("/api/public/zakupki/{reg_number}/reserve")
def reserve_procurement(
    reg_number: str,
    req: ReserveCheapestRequest | None = None,
    current_user: dict = Depends(public_api_auth_required),
):
    reg = (reg_number or "").strip()
    if not reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")

    _, pipeline = _view_service()
    zakupka = pipeline.db.zakupki.get_by_id(reg)
    if not zakupka:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zakupka not found")
    allowed_statuses = {
        ZakupkaStatus.URL_READY,
        ZakupkaStatus.STAGE4_DONE,
        ZakupkaStatus.STAGE4_ERROR,
        ZakupkaStatus.LISTINGS_FRESH,
        ZakupkaStatus.LISTINGS_STALE,
    }
    if str(getattr(zakupka, "status", "") or "").strip() not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Zakupka is not available for reservation")

    reservation = pipeline.db.zakupka_reservations.reserve_procurement(
        reg_number=reg,
        reserved_by=current_user["email"],
        ttl_hours=settings.reservation_ttl_hours,
    )
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zakupka not found")
    if reservation.get("reserved_by_other"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Zakupka is already reserved")
    return {
        "status": "ok",
        "reg_number": reservation["reg_number"],
        "expires_at": reservation["expires_at"],
        "already_reserved": bool(reservation.get("already_reserved", False)),
    }


@router.post("/api/public/zakupki/{reg_number}/unreserve")
def unreserve_procurement(
    reg_number: str,
    current_user: dict = Depends(public_api_auth_required),
):
    reg = (reg_number or "").strip()
    if not reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")

    _, pipeline = _view_service()
    if not pipeline.db.zakupki.get_by_id(reg):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zakupka not found")

    active = None
    if hasattr(pipeline.db.zakupka_reservations, "get_active_by_reg"):
        active = pipeline.db.zakupka_reservations.get_active_by_reg(reg)

    if not active:
        return {"status": "ok", "reg_number": reg, "already_released": True}

    owner = str(active.get("reserved_by") or "").strip().lower()
    current_owner = str(current_user.get("email") or "").strip().lower()
    if owner and owner != current_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reservation is not owned by current user")

    cancelled = pipeline.db.zakupka_reservations.cancel_active(reg, reserved_by=current_user["email"])
    return {"status": "ok", "reg_number": reg, "already_released": not cancelled}


@router.post("/api/public/zakupki/{reg_number}/favorite")
def favorite_procurement(
    reg_number: str,
    current_user: dict = Depends(public_api_auth_required),
):
    reg = (reg_number or "").strip()
    if not reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")

    _, pipeline = _view_service()
    if not pipeline.db.zakupki.get_by_id(reg):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")
    if not hasattr(pipeline.db, "public_favorites"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Favorites unavailable")

    pipeline.db.public_favorites.add_favorite(reg, current_user["email"])
    return {"status": "ok", "reg_number": reg, "is_favorite": True}


@router.post("/api/public/zakupki/{reg_number}/unfavorite")
def unfavorite_procurement(
    reg_number: str,
    current_user: dict = Depends(public_api_auth_required),
):
    reg = (reg_number or "").strip()
    if not reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")

    _, pipeline = _view_service()
    if not pipeline.db.zakupki.get_by_id(reg):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reg_number")
    if not hasattr(pipeline.db, "public_favorites"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Favorites unavailable")

    pipeline.db.public_favorites.remove_favorite(reg, current_user["email"])
    return {"status": "ok", "reg_number": reg, "is_favorite": False}


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
