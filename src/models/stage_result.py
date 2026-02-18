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

    stage: int
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Преобразует в словарь для JSON."""
        return {
            "stage": self.stage,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
        }

    def __str__(self) -> str:
        status = "[OK]" if self.success else "[ERROR]"
        return f"{status} Stage {self.stage}: {self.message}"
