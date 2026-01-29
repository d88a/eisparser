"""
Сервис для работы с базой данных.
Объединяет все репозитории и инициализирует БД.
"""
from pathlib import Path
from config.settings import settings
from repositories import ZakupkaRepository, AIResultRepository, ListingRepository, UserRepository, DecisionRepository
from repositories.user_override_repo import UserOverrideRepository
from repositories.user_selection_repo import UserSelectionRepository
from utils.logger import get_logger


class DatabaseService:
    """
    Единая точка доступа к базе данных.
    Содержит все репозитории и управляет инициализацией.
    """
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: Путь к БД. Если не указан, берётся из settings.
        """
        self.db_path = db_path or settings.database_path
        self.logger = get_logger("DatabaseService")
        
        # Инициализируем репозитории
        self.zakupki = ZakupkaRepository(self.db_path)
        self.ai_results = AIResultRepository(self.db_path)
        self.listings = ListingRepository(self.db_path)
        self.users = UserRepository(self.db_path)
        self.decisions = DecisionRepository(self.db_path)
        self.user_overrides = UserOverrideRepository(self.db_path)
        self.user_selections = UserSelectionRepository(self.db_path)
        
        self.logger.debug(f"DatabaseService инициализирован: {self.db_path}")
    
    def init_database(self) -> bool:
        """
        Создаёт все таблицы в БД.
        
        Returns:
            True если успешно
        """
        self.logger.info("Инициализация базы данных...")
        
        # Создаём директорию для БД
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Создаём таблицы
        success = all([
            self.zakupki.create_table(),
            self.ai_results.create_table(),
            self.listings.create_table(),
            self.users.create_table(),
            self.decisions.create_table(),
            self.user_overrides.create_table(),
            self.user_selections.create_table()
        ])
        
        if success:
            self.logger.info("База данных инициализирована успешно")
        else:
            self.logger.error("Ошибка инициализации базы данных")
        
        return success
    
    def get_statistics(self) -> dict:
        """Возвращает статистику по БД."""
        return {
            "zakupki_count": len(self.zakupki.get_all()),
            "ai_results_count": len(self.ai_results.get_all()),
            "listings_count": self.listings.count(),
            "users_count": self.users.count(),
            "decisions_count": len(self.decisions.get_all())
        }
        
    def get_zakupki_for_stage(self, user_id: int, stage: int) -> list:
        """
        Возвращает список закупок, одобренных пользователем на данном этапе.
        
        Args:
            user_id: ID пользователя
            stage: Номер этапа
            
        Returns:
            Список объектов Zakupka
        """
        # 1. Получаем список reg_number одобренных закупок
        approved_ids = self.decisions.get_approved_reg_numbers(user_id, stage)
        
        if not approved_ids:
            return []
            
        # 2. Загружаем сами закупки
        return self.zakupki.get_by_reg_numbers(approved_ids)


# Глобальный экземпляр (singleton pattern)
_db_service: DatabaseService = None


def get_database_service(db_path: str = None) -> DatabaseService:
    """
    Получает или создаёт singleton DatabaseService.
    """
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService(db_path)
    return _db_service

