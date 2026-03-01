"""Auth and HTML page routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse

from .common import (
    admin_required,
    create_admin_token,
    get_current_admin,
    templates,
    user_access_required,
)


router = APIRouter()


@router.get("/admin/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/admin/login")
async def login_submit(request: Request):
    from urllib.parse import parse_qs

    from config.settings import settings

    body = await request.body()
    password = None
    if body:
        data = parse_qs(body.decode("utf-8"))
        password = data.get("password", [None])[0]

    if password == settings.admin_password:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
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


@router.get("/")
def read_root(request: Request, admin: Optional[bool] = Depends(get_current_admin)):
    if admin:
        return templates.TemplateResponse("index.html", {"request": request, "is_admin": True})
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/stage2")
def read_stage2(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("stage2.html", {"request": request, "is_admin": True})


@router.get("/stage3")
def read_stage3(request: Request, admin: bool = Depends(admin_required)):
    return templates.TemplateResponse("stage3.html", {"request": request, "is_admin": True})


@router.get("/stage4")
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
