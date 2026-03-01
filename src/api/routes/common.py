"""Shared API route helpers: auth, templates, request models."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from config.settings import settings


base_dir = Path(__file__).parent.parent.parent
templates = Jinja2Templates(directory=str(base_dir / "web" / "templates"))


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


class BatchStage2Request(BaseModel):
    limit: Optional[int] = None


class BatchStage3Request(BaseModel):
    limit: Optional[int] = None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad_len))


def _sign_admin_payload(payload_b64: str) -> str:
    secret = (settings.admin_token_secret or settings.admin_password).encode("utf-8")
    sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_admin_token() -> str:
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + max(60, int(settings.admin_token_ttl_seconds or 0)),
        "type": "admin",
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    signature = _sign_admin_payload(payload_b64)
    return f"{payload_b64}.{signature}"


def verify_admin_token(token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    payload_b64, signature = token.split(".", 1)
    expected = _sign_admin_payload(payload_b64)
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return False
    if payload.get("type") != "admin":
        return False
    exp = int(payload.get("exp", 0) or 0)
    return exp > int(time.time())


def get_current_admin(request: Request):
    token = request.cookies.get("admin_token")
    if not verify_admin_token(token):
        return None
    return True


def admin_required(admin: bool = Depends(get_current_admin)):
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin access required",
        )
    return True


def user_access_required(admin: bool = Depends(get_current_admin)):
    """User API access policy controlled by USER_ACCESS_MODE."""
    mode = (settings.user_access_mode or "PUBLIC").strip().upper()
    if mode == "PUBLIC":
        return True
    if admin:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User authentication required",
    )
