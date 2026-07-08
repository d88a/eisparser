"""Public favorite model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PublicFavorite:
    id: Optional[int]
    reg_number: str
    user_email: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "PublicFavorite":
        return cls(
            id=data.get("id"),
            reg_number=data.get("reg_number") or "",
            user_email=(data.get("user_email") or "").strip().lower(),
            created_at=data.get("created_at") or "",
        )
