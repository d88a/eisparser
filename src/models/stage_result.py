"""
Модель результата выполнения этапа.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class StageResult:
    """
    Унифицированный результат выполнения этапа пайплайна.
    Используется для CLI и дашборда.
    """
    
    stage: int                          # Номер этапа (1, 2, 3, 4)
    success: bool                       # Успешно ли выполнен
    message: str                        # Сообщение для пользователя
    data: Dict[str, Any] = field(default_factory=dict)  # Данные для отображения
    errors: List[str] = field(default_factory=list)     # Список ошибок
    
    def to_dict(self) -> dict:
        """Преобразует в словарь для JSON."""
        return {
            "stage": self.stage,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors
        }
    
    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"{status} Stage {self.stage}: {self.message}"
