"""Reservation model for listing monetization MVP."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ListingReservation:
    """Represents reservation of a listing for a limited time window."""

    id: Optional[int]
    listing_id: int
    reg_number: str
    reserved_by: str
    status: str
    reserved_at: str
    expires_at: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "ListingReservation":
        return cls(
            id=data.get("id"),
            listing_id=int(data.get("listing_id") or 0),
            reg_number=data.get("reg_number") or "",
            reserved_by=data.get("reserved_by") or "anon",
            status=data.get("status") or "active",
            reserved_at=data.get("reserved_at") or "",
            expires_at=data.get("expires_at") or "",
            created_at=data.get("created_at") or "",
            updated_at=data.get("updated_at") or "",
        )
