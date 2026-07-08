"""
Сервис для работы с базой данных.
Объединяет все репозитории и инициализирует БД.
"""
from pathlib import Path
from typing import Optional
from config.settings import settings
from models.zakupka import Zakupka
from repositories import (
    ZakupkaRepository,
    AIResultRepository,
    ListingRepository,
    ListingReservationRepository,
    ZakupkaReservationRepository,
    PublicFavoriteRepository,
    UserRepository,
    DecisionRepository,
)
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
        self.database_url = settings.database_url
        self.logger = get_logger("DatabaseService")
        
        # Инициализируем репозитории
        self.zakupki = ZakupkaRepository(self.db_path, self.database_url)
        self.ai_results = AIResultRepository(self.db_path, self.database_url)
        self.listings = ListingRepository(self.db_path, self.database_url)
        self.listing_reservations = ListingReservationRepository(self.db_path, self.database_url)
        self.zakupka_reservations = ZakupkaReservationRepository(self.db_path, self.database_url)
        self.public_favorites = PublicFavoriteRepository(self.db_path, self.database_url)
        self.users = UserRepository(self.db_path, self.database_url)
        self.decisions = DecisionRepository(self.db_path, self.database_url)
        self.user_overrides = UserOverrideRepository(self.db_path, self.database_url)
        self.user_selections = UserSelectionRepository(self.db_path, self.database_url)
        
        if self.database_url:
            self.logger.info("Database backend: PostgreSQL (%s)", self.database_url)
        else:
            self.logger.info("Database backend: SQLite (%s)", self.db_path)
    
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
            self.listing_reservations.create_table(),
            self.zakupka_reservations.create_table(),
            self.public_favorites.create_table(),
            self.users.create_table(),
            self.decisions.create_table(),
            self.user_overrides.create_table(),
            self.user_selections.create_table()
        ])

        # Ensure performance-critical indexes for Stage 2 queries.
        if success:
            try:
                with self.zakupki.get_connection() as conn:
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_zakupki_status ON zakupki(status)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_ai_results_reg_number ON ai_results(reg_number)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_zakupki_processed_at ON zakupki(processed_at)"
                    )
                    conn.commit()
                self.logger.info("Stage 2 indexes ensured")
            except Exception as e:
                self.logger.error(f"Failed to ensure Stage 2 indexes: {e}")

        # Cleanup legacy decisions marked as "selected" to avoid stale stage logic.
        try:
            removed = self.decisions.delete_by_decision_value("selected")
            if removed:
                self.logger.info(f"Deleted legacy decisions with selected: {removed}")
        except Exception as e:
            self.logger.error(f"Failed to cleanup selected decisions: {e}")
        
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
            "listing_reservations_count": len(self.listing_reservations.get_all()),
            "zakupka_reservations_count": len(self.zakupka_reservations.get_all()),
            "public_favorites_count": len(self.public_favorites.get_all()),
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

    def _get_stage2_overwrite_page(self, offset: int = 0, limit: int = 100) -> list[Zakupka]:
        """Returns one overwrite-compatible page for Stage 2."""
        offset = max(0, int(offset or 0))
        limit = max(1, int(limit or 100))
        with self.zakupki.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT z.*
                FROM zakupki z
                WHERE z.status IN (?, ?)
                  AND COALESCE(TRIM(z.combined_text), '') <> ''
                ORDER BY
                    CASE WHEN z.processed_at IS NULL THEN 1 ELSE 0 END,
                    z.processed_at DESC,
                    z.update_date DESC
                LIMIT ? OFFSET ?
                """,
                ("raw", "ai_error", limit, offset),
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            row_dict = self.zakupki.row_to_dict(row)
            if row_dict:
                items.append(Zakupka.from_dict(row_dict))
        return items

    def get_stage2_pending_items(
        self,
        overwrite: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list:
        """
        Returns Stage 2 pending items.

        - limit=None: full queue (loaded in pages to avoid one heavy query)
        - limit=N: one page only
        """
        offset = max(0, int(offset or 0))
        page_size = max(1, int(limit or 100)) if limit is not None else 500

        if limit is not None:
            if overwrite:
                return self._get_stage2_overwrite_page(offset=offset, limit=page_size)
            items, _ = self.get_stage2_pending_page(offset=offset, limit=page_size)
            return items

        all_items: list[Zakupka] = []
        current_offset = offset
        while True:
            if overwrite:
                page_items = self._get_stage2_overwrite_page(offset=current_offset, limit=page_size)
            else:
                page_items, _ = self.get_stage2_pending_page(offset=current_offset, limit=page_size)

            if not page_items:
                break

            all_items.extend(page_items)
            current_offset += len(page_items)
            if len(page_items) < page_size:
                break

        return all_items

    def get_stage2_pending_page(self, offset: int = 0, limit: int = 20) -> tuple[list[Zakupka], int]:
        """Returns paginated Stage 2 pending purchases and total count."""
        offset = max(0, int(offset or 0))
        limit = max(1, int(limit or 20))

        where_sql = """
            FROM zakupki z
            WHERE z.status IN (?, ?)
              AND COALESCE(TRIM(z.combined_text), '') <> ''
              AND (
                    z.status = ?
                    OR NOT EXISTS (
                        SELECT 1
                        FROM ai_results a
                        WHERE a.reg_number = z.reg_number
                    )
              )
        """
        params = ("raw", "ai_error", "ai_error")

        with self.zakupki.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS c {where_sql}", params)
            count_row = cur.fetchone()
            total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

            cur.execute(
                f"""
                SELECT z.*
                {where_sql}
                ORDER BY
                    CASE WHEN z.processed_at IS NULL THEN 1 ELSE 0 END,
                    z.processed_at DESC,
                    z.update_date DESC
                LIMIT ? OFFSET ?
                """,
                params + (limit, offset),
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            row_dict = self.zakupki.row_to_dict(row)
            if row_dict:
                items.append(Zakupka.from_dict(row_dict))

        return items, total


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

