"""Service wrapper around AI result repository methods."""

from typing import Optional

from models.ai_result import AIResult
from repositories.ai_result_repo import AIResultRepository
from utils.logger import get_logger


class AIService:
    """Repository facade used by pipeline and API."""

    def __init__(self, ai_result_repo: AIResultRepository):
        self.repo = ai_result_repo
        self.logger = get_logger("AIService")

    def save_result(self, result: AIResult) -> bool:
        """Сохраняет результат ИИ-анализа."""
        saved = self.repo.save(result)
        if saved:
            self.logger.info(f"Сохранён результат для: {result.reg_number}")
        return saved

    def get_result(self, reg_number: str) -> Optional[AIResult]:
        """Получает результат анализа по номеру закупки."""
        return self.repo.get_by_id(reg_number)

    def get_all_results(self) -> list:
        """Получает все результаты анализа."""
        return self.repo.get_all()

    def update_rooms_parsed(self, reg_number: str, rooms_parsed: str) -> bool:
        """Обновляет распарсенные комнаты."""
        return self.repo.update_rooms_parsed(reg_number, rooms_parsed)

    def count(self) -> int:
        """Возвращает количество результатов."""
        return len(self.repo.get_all())
