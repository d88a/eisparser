"""
Модель пользователя.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """
    Пользователь системы.
    
    Attributes:
        id: Уникальный идентификатор (автогенерируется)
        email: Email пользователя
        role: Роль (admin, user и т.д.)
        created_at: Дата создания
    """
    email: str
    role: str = "admin"
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    @classmethod
    def from_row(cls, row) -> "User":
        """Создаёт User из sqlite3.Row."""
        return cls(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )
