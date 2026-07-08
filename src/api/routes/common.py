"""Shared API route helpers: auth, templates, request models."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
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


class ReserveCheapestRequest(BaseModel):
    reserved_by: Optional[str] = "anon"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad_len))


def _sign_admin_payload(payload_b64: str) -> str:
    secret = (settings.admin_token_secret or settings.admin_password).encode("utf-8")
    sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def _public_auth_secret() -> bytes:
    return (settings.admin_token_secret or settings.admin_password).encode("utf-8")


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


def create_public_token(user_id: int, email: str, ttl_seconds: int = 7 * 24 * 60 * 60) -> str:
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + max(300, int(ttl_seconds or 0)),
        "type": "public",
        "user_id": int(user_id),
        "email": str(email or "").strip().lower(),
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    signature = _b64url_encode(hmac.new(_public_auth_secret(), payload_b64.encode("utf-8"), hashlib.sha256).digest())
    return f"{payload_b64}.{signature}"


def verify_public_token(token: Optional[str]) -> Optional[dict]:
    if not token or "." not in token:
        return None
    payload_b64, signature = token.split(".", 1)
    expected = _b64url_encode(hmac.new(_public_auth_secret(), payload_b64.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None
    if payload.get("type") != "public":
        return None
    if int(payload.get("exp", 0) or 0) <= int(time.time()):
        return None
    user_id = int(payload.get("user_id", 0) or 0)
    email = str(payload.get("email") or "").strip().lower()
    if user_id <= 0 or not email:
        return None
    return {"user_id": user_id, "email": email}


def hash_public_password(password: str, iterations: int = 200_000) -> str:
    raw = (password or "").encode("utf-8")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw, salt, max(100_000, int(iterations)))
    return "pbkdf2_sha256$%d$%s$%s" % (
        max(100_000, int(iterations)),
        _b64url_encode(salt),
        _b64url_encode(digest),
    )


def verify_public_password(password: str, encoded_hash: Optional[str]) -> bool:
    raw_hash = str(encoded_hash or "")
    parts = raw_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = max(100_000, int(parts[1]))
        salt = _b64url_decode(parts[2])
        expected = _b64url_decode(parts[3])
    except Exception:
        return False
    got = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iterations)
    return hmac.compare_digest(got, expected)


def get_current_admin(request: Request):
    token = request.cookies.get("admin_token")
    if not verify_admin_token(token):
        return None
    return True


def get_current_public_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("public_token")
    return verify_public_token(token)


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


def public_api_auth_required(current_user: Optional[dict] = Depends(get_current_public_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth required",
        )
    return current_user
