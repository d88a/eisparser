"""
Модель решения пользователя.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Decision:
    """
    Решение пользователя по закупке.
    
    Attributes:
        user_id: ID пользователя
        reg_number: Номер закупки
        stage: Номер этапа (1-4)
        decision: Решение ('approved', 'rejected', 'skipped')
        comment: Комментарий (опционально)
        id: Уникальный идентификатор (автогенерируется)
        created_at: Дата создания
    """
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
        """Создаёт Decision из sqlite3.Row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            reg_number=row["reg_number"],
            stage=row["stage"],
            decision=row["decision"],
            comment=row["comment"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )
