"""Decision model."""

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
class Decision:
    user_id: int
    reg_number: str
    stage: int
    decision: str
    comment: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @classmethod
    def from_row(cls, row) -> "Decision":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            reg_number=row["reg_number"],
            stage=row["stage"],
            decision=row["decision"],
            comment=row["comment"],
            created_at=_to_datetime(row["created_at"]),
        )
