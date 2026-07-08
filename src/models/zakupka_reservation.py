"""Reservation model for full procurement reservation."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ZakupkaReservation:
    id: Optional[int]
    reg_number: str
    reserved_by: str
    status: str
    reserved_at: str
    expires_at: str
    created_at: str
    updated_at: str
    end_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ZakupkaReservation":
        return cls(
            id=data.get("id"),
            reg_number=data.get("reg_number") or "",
            reserved_by=data.get("reserved_by") or "anon",
            status=data.get("status") or "active",
            reserved_at=data.get("reserved_at") or "",
            expires_at=data.get("expires_at") or "",
            created_at=data.get("created_at") or "",
            updated_at=data.get("updated_at") or "",
            end_reason=data.get("end_reason"),
        )
