"""
Сервис для ИИ-анализа закупок через Gemini.
"""
from typing import Optional, Dict, Any
from models.ai_result import AIResult
from models.zakupka import Zakupka
from repositories.ai_result_repo import AIResultRepository
from utils.logger import get_logger
from config.settings import settings


class AIService:
    """
    Сервис для работы с ИИ (Gemini).
    Обрабатывает тексты закупок и извлекает параметры.
    """
    
    def __init__(self, ai_result_repo: AIResultRepository):
        self.repo = ai_result_repo
        self.logger = get_logger("AIService")
        self._client = None
    
    def _get_client(self):
        """Ленивая инициализация клиента Gemini."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                self._client = genai.GenerativeModel(settings.gemini_model)
                self.logger.info(f"Gemini инициализирован: {settings.gemini_model}")
            except Exception as e:
                self.logger.error(f"Ошибка инициализации Gemini: {e}")
                raise
        return self._client
    
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
