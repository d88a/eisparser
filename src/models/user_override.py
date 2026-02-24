"""User override model."""

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
class UserOverride:
    reg_number: str
    field_name: str
    value: str
    user_id: int = 1
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_row(cls, row) -> "UserOverride":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            reg_number=row["reg_number"],
            field_name=row["field_name"],
            value=row["value"],
            created_at=_to_datetime(row["created_at"]),
        )
