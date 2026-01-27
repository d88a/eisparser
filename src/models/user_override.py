"""
Модель пользовательских переопределений AI-результатов.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class UserOverride:
    """
    Хранит пользовательские корректировки AI-результата.
    AI-результат остаётся неизменным (read-only).
    """
    reg_number: str
    field_name: str     # e.g. "city", "price_rub", "area_min_m2"
    value: str          # Новое значение от пользователя
    user_id: int = 1
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_row(cls, row) -> 'UserOverride':
        """Создаёт объект из строки БД."""
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            reg_number=row['reg_number'],
            field_name=row['field_name'],
            value=row['value'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now()
        )
