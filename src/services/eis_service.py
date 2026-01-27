"""
Сервис для загрузки закупок с ЕИС.
"""
from typing import List, Optional
from models.zakupka import Zakupka
from repositories.zakupka_repo import ZakupkaRepository
from utils.logger import get_logger
from config.settings import settings


class EISService:
    """
    Сервис для работы с ЕИС (zakupki.gov.ru).
    Оборачивает логику загрузки и сохранения закупок.
    """
    
    def __init__(self, zakupka_repo: ZakupkaRepository):
        self.repo = zakupka_repo
        self.logger = get_logger("EISService")
    
    def save_zakupka(self, zakupka: Zakupka) -> bool:
        """Сохраняет закупку в БД."""
        result = self.repo.save(zakupka)
        if result:
            self.logger.info(f"Сохранена закупка: {zakupka.reg_number}")
        else:
            self.logger.error(f"Ошибка сохранения: {zakupka.reg_number}")
        return result
    
    def get_zakupka(self, reg_number: str) -> Optional[Zakupka]:
        """Получает закупку по номеру."""
        return self.repo.get_by_id(reg_number)
    
    def get_all_zakupki(self) -> List[Zakupka]:
        """Получает все закупки."""
        return self.repo.get_all()
    
    def get_zakupki_with_links(self) -> List[Zakupka]:
        """Получает закупки с заполненными ссылками 2ГИС."""
        return self.repo.get_with_two_gis_url()
    
    def update_two_gis_url(self, reg_number: str, url: str) -> bool:
        """Обновляет ссылку 2ГИС для закупки."""
        result = self.repo.update_two_gis_url(reg_number, url)
        if result:
            self.logger.info(f"✅ Сохранена ссылка в БД для {reg_number}")
        else:
            self.logger.warning(f"⚠️ Не удалось сохранить ссылку для {reg_number} (rowcount=0)")
        return result
    
    def delete_zakupka(self, reg_number: str) -> bool:
        """Удаляет закупку."""
        result = self.repo.delete(reg_number)
        if result:
            self.logger.info(f"Удалена закупка: {reg_number}")
        return result
    
    def get_by_reg_numbers(self, reg_numbers: List[str]) -> List[Zakupka]:
        """Получает список закупок по списку номеров."""
        return self.repo.get_by_reg_numbers(reg_numbers)

    def count(self) -> int:
        """Возвращает количество закупок."""
        return len(self.repo.get_all())
