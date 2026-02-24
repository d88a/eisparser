"""User model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def _to_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


@dataclass
class User:
    email: str
    role: str = "admin"
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=_to_datetime(row["created_at"]),
        )
