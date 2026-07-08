"""User selection model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _to_datetime(value):
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.now()
    return datetime.now()


@dataclass
class UserSelection:
    user_id: int
    reg_number: str
    selected_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "UserSelection":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            reg_number=row["reg_number"],
            selected_at=_to_datetime(row["selected_at"]),
        )
