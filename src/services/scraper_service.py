"""
Сервис для сбора объявлений с 2ГИС.
"""
from typing import List, Optional
from models.listing import Listing, ListingResult
from repositories.listing_repo import ListingRepository
from utils.logger import get_logger
from config.settings import settings


class ScraperService:
    """
    Сервис для сбора объявлений недвижимости.
    Оборачивает логику парсинга 2ГИС.
    """
    
    def __init__(self, listing_repo: ListingRepository):
        self.repo = listing_repo
        self.logger = get_logger("ScraperService")
    
    def collect_listings(
        self,
        url: str,
        top_n: int = 20,
        headless: bool = None,
        proxy: str = None,
        get_details: bool = False
    ) -> ListingResult:
        """
        Собирает объявления по URL.
        
        Args:
            url: URL поиска 2ГИС
            top_n: Количество объявлений
            headless: Безголовый режим
            proxy: Прокси-сервер
            get_details: Получать детали (год постройки)
        
        Returns:
            ListingResult с собранными объявлениями
        """
        if headless is None:
            headless = settings.stage4_headless
        
        if proxy is None:
            proxy = settings.proxy_url
        
        self.logger.info(f"Сбор {top_n} объявлений...")
        self.logger.debug(f"URL: {url[:80]}...")
        
        try:
            # Импортируем scraper из существующего модуля
            from realty_scraper.two_gis_playwright import collect_top_listings
            
            result = collect_top_listings(
                url=url,
                top_n=top_n,
                headless=headless,
                proxy=proxy,
                get_details=get_details
            )
            
            self.logger.info(f"Собрано {result.actual_n} объявлений")
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка сбора: {e}")
            return ListingResult(
                query_url=url,
                top_n=top_n,
                error=str(e)
            )
    
    def save_listings(
        self,
        reg_number: str,
        listings: List[Listing],
        query_url: str = None
    ) -> int:
        """
        Сохраняет объявления в БД.
        
        Args:
            reg_number: Номер закупки
            listings: Список объявлений
            query_url: URL запроса
        
        Returns:
            Количество сохранённых записей
        """
        count = self.repo.save_batch(reg_number, listings, query_url)
        self.logger.info(f"Сохранено {count} объявлений для {reg_number}")
        return count
    
    def get_listings(self, reg_number: str) -> List[Listing]:
        """Получает объявления для закупки."""
        return self.repo.get_for_zakupka(reg_number)
    
    def delete_listings(self, reg_number: str) -> int:
        """Удаляет объявления для закупки."""
        count = self.repo.delete_for_zakupka(reg_number)
        if count > 0:
            self.logger.info(f"Удалено {count} объявлений для {reg_number}")
        return count
    
    def count(self) -> int:
        """Возвращает общее количество объявлений."""
        return self.repo.count()
