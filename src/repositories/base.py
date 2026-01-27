"""
Базовый класс репозитория.
"""
import sqlite3
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Optional, List, TypeVar, Generic
from pathlib import Path

from utils.logger import get_logger

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Абстрактный базовый репозиторий.
    Предоставляет общую логику работы с SQLite.
    """
    
    def __init__(self, db_path: str, max_retries: int = 3):
        self.db_path = db_path
        self.max_retries = max_retries
        self.logger = get_logger(self.__class__.__name__)
        self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Создаёт директорию для БД если не существует."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_with_retry(self, operation, *args, **kwargs):
        """
        Выполняет операцию с повторными попытками при блокировке.
        """
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                return operation(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    retry_count += 1
                    self.logger.warning(
                        f"БД заблокирована, попытка {retry_count}/{self.max_retries}"
                    )
                    time.sleep(1)
                else:
                    raise
        self.logger.error(f"Операция не выполнена после {self.max_retries} попыток")
        return None
    
    @abstractmethod
    def create_table(self) -> bool:
        """Создаёт таблицу в БД."""
        pass
    
    @abstractmethod
    def save(self, entity: T) -> bool:
        """Сохраняет сущность."""
        pass
    
    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]:
        """Получает сущность по ID."""
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """Получает все сущности."""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """Удаляет сущность."""
        pass
