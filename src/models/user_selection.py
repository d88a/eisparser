"""
Модель пользовательской выборки закупок.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class UserSelection:
    """Пользовательская выборка закупки для анализа."""
    
    user_id: int                            # ID пользователя
    reg_number: str                         # Номер закупки
    selected_at: datetime = field(default_factory=datetime.now)  # Время выбора
    id: Optional[int] = None                # ID записи
    
    @classmethod
    def from_row(cls, row) -> 'UserSelection':
        """Создаёт объект из строки БД."""
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            reg_number=row['reg_number'],
            selected_at=datetime.fromisoformat(row['selected_at']) if row['selected_at'] else datetime.now()
        )
