"""Auth and HTML page routes."""

from urllib.parse import parse_qs
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse

from models.user import User
from .common import (
    admin_required,
    create_admin_token,
    create_public_token,
    get_current_admin,
    get_current_public_user,
    hash_public_password,
    templates,
    user_access_required,
    verify_public_password,
)


router = APIRouter()


def _safe_public_next(raw_next: Optional[str]) -> str:
    value = (raw_next or "").strip()
    if value.startswith("/"):
        return value
    return "/public/zakupki"


async def _read_public_auth_form(request: Request) -> dict:
    body = await request.body()
    data = parse_qs(body.decode("utf-8")) if body else {}
    return {
        "email": (data.get("email", [""])[0] or "").strip().lower(),
        "password": data.get("password", [""])[0] or "",
        "password_confirm": data.get("password_confirm", [""])[0] or "",
        "next": _safe_public_next(data.get("next", [""])[0]),
    }


@router.get("/admin/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/admin/login")
async def login_submit(request: Request):
    from config.settings import settings

    body = await request.body()
    password = None
    if body:
        data = parse_qs(body.decode("utf-8"))
        password = data.get("password", [None])[0]

    if password == settings.admin_password:
        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        token = create_admin_token()
        response.set_cookie(
            key="admin_token",
            value=token,
            httponly=True,
            path="/",
            max_age=max(60, int(settings.admin_token_ttl_seconds or 0)),
            samesite="lax",
            secure=bool(request.url.scheme == "https"),
        )
        return response

    return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный пароль"})


@router.get("/admin/logout")
def logout():
    response = RedirectResponse(url="/admin/login")
    response.delete_cookie("admin_token")
    return response


@router.get("/public/login")
def public_login_page(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_public_user),
):
    if current_user:
        return RedirectResponse(url=_safe_public_next(next), status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "public_login.html",
        {
            "request": request,
            "next": _safe_public_next(next),
            "error": error,
            "is_public_authenticated": False,
            "public_user_email": None,
        },
    )


@router.get("/public/register")
def public_register_page(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_public_user),
):
    if current_user:
        return RedirectResponse(url=_safe_public_next(next), status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "public_register.html",
        {
            "request": request,
            "next": _safe_public_next(next),
            "error": error,
            "is_public_authenticated": False,
            "public_user_email": None,
        },
    )


@router.post("/api/public/register")
async def public_register_submit(request: Request):
    from ..app import get_pipeline

    payload = await _read_public_auth_form(request)
    email = payload["email"]
    password = payload["password"]
    password_confirm = payload["password_confirm"]
    next_url = payload["next"]

    if not email:
        return RedirectResponse(url=f"/public/register?next={next_url}&error=Email+is+required", status_code=302)
    if len(password) < 8:
        return RedirectResponse(
            url=f"/public/register?next={next_url}&error=Password+must+be+at+least+8+characters",
            status_code=302,
        )
    if password != password_confirm:
        return RedirectResponse(url=f"/public/register?next={next_url}&error=Passwords+do+not+match", status_code=302)

    pipeline = get_pipeline()
    users_repo = pipeline.db.users
    if users_repo.get_by_email(email):
        return RedirectResponse(url=f"/public/register?next={next_url}&error=Email+already+exists", status_code=302)

    user = users_repo.create_public_user(email=email, password_hash=hash_public_password(password))
    if not user:
        return RedirectResponse(
            url=f"/public/register?next={next_url}&error=Failed+to+create+account",
            status_code=302,
        )

    response = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="public_token",
        value=create_public_token(user.id or 0, user.email),
        httponly=True,
        path="/",
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=bool(request.url.scheme == "https"),
    )
    return response


@router.post("/api/public/login")
async def public_login_submit(request: Request):
    from ..app import get_pipeline

    payload = await _read_public_auth_form(request)
    email = payload["email"]
    password = payload["password"]
    next_url = payload["next"]

    pipeline = get_pipeline()
    user: Optional[User] = pipeline.db.users.get_by_email(email) if email else None
    if not user or not verify_public_password(password, user.password_hash):
        return RedirectResponse(url=f"/public/login?next={next_url}&error=Invalid+email+or+password", status_code=302)

    response = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="public_token",
        value=create_public_token(user.id or 0, user.email),
        httponly=True,
        path="/",
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=bool(request.url.scheme == "https"),
    )
    return response


@router.post("/api/public/logout")
def public_logout(next: Optional[str] = None):
    response = RedirectResponse(url=_safe_public_next(next), status_code=status.HTTP_302_FOUND)
    response.delete_cookie("public_token", path="/")
    return response


@router.get("/")
def read_root(request: Request):
    return RedirectResponse(url="/public/zakupki", status_code=status.HTTP_302_FOUND)


@router.get("/admin")
def read_admin_dashboard(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("index.html", {"request": request, "is_admin": True})


@router.get("/admin/stage2")
def read_stage2(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("stage2.html", {"request": request, "is_admin": True})


@router.get("/admin/stage3")
def read_stage3(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("stage3.html", {"request": request, "is_admin": True})


@router.get("/admin/stage4")
def read_stage4(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("stage4.html", {"request": request, "is_admin": True})


@router.get("/user/available")
def read_user_available(
    request: Request,
    _user_access: bool = Depends(user_access_required),
    admin: Optional[bool] = Depends(get_current_admin),
):
    return templates.TemplateResponse("user_available.html", {"request": request, "is_admin": bool(admin)})


@router.get("/user/selections")
def read_user_selections(
    request: Request,
    _user_access: bool = Depends(user_access_required),
    admin: Optional[bool] = Depends(get_current_admin),
):
    return templates.TemplateResponse("user_selections.html", {"request": request, "is_admin": bool(admin)})
