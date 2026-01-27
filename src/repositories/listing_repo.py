"""
Репозиторий для объявлений из 2ГИС.
"""
from typing import Optional, List
from datetime import datetime
from .base import BaseRepository
from models.listing import Listing


class ListingRepository(BaseRepository[Listing]):
    """Репозиторий для CRUD операций с объявлениями."""
    
    def create_table(self) -> bool:
        """Создаёт таблицу listings."""
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS listings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        zakupka_reg_number TEXT NOT NULL,
                        rank INTEGER,
                        price_rub INTEGER NOT NULL,
                        address TEXT,
                        rooms INTEGER,
                        area_m2 REAL,
                        floor INTEGER,
                        building_floors INTEGER,
                        building_year INTEGER,
                        two_gis_url TEXT,
                        external_source TEXT,
                        external_url TEXT,
                        fetched_at TEXT NOT NULL,
                        query_url TEXT,
                        FOREIGN KEY (zakupka_reg_number) REFERENCES zakupki(reg_number)
                    )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listings_zakupka ON listings(zakupka_reg_number)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_rub)"
                )
                conn.commit()
                return True
        
        return self.execute_with_retry(_create) or False
    
    def save(self, listing: Listing) -> bool:
        """Сохраняет одно объявление (без reg_number)."""
        # Этот метод не используется напрямую, используйте save_batch
        raise NotImplementedError("Используйте save_batch для сохранения listings")
    
    def save_batch(self, reg_number: str, listings: List[Listing], query_url: str = None) -> int:
        """
        Сохраняет список объявлений.
        Сначала удаляет старые записи для этой закупки.
        """
        # Удаляем старые
        deleted = self.delete_for_zakupka(reg_number)
        if deleted > 0:
            self.logger.info(f"Удалено {deleted} старых listings для {reg_number}")
        
        if not listings:
            return 0
        
        def _save_batch():
            fetched_at = datetime.now().isoformat()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                inserted = 0
                
                for listing in listings:
                    data = listing.to_dict() if hasattr(listing, 'to_dict') else listing
                    cursor.execute("""
                        INSERT INTO listings (
                            zakupka_reg_number, rank, price_rub, address,
                            rooms, area_m2, floor, building_floors, building_year,
                            two_gis_url, external_source, external_url,
                            fetched_at, query_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        reg_number,
                        data.get('rank'),
                        data.get('price_rub'),
                        data.get('address'),
                        data.get('rooms'),
                        data.get('area_m2'),
                        data.get('floor'),
                        data.get('building_floors'),
                        data.get('building_year'),
                        data.get('two_gis_url'),
                        data.get('external_source'),
                        data.get('external_url'),
                        fetched_at,
                        query_url
                    ))
                    inserted += 1
                
                conn.commit()
                return inserted
        
        return self.execute_with_retry(_save_batch) or 0
    
    def get_by_id(self, id: str) -> Optional[Listing]:
        """Получает объявление по ID."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listings WHERE id = ?", (id,))
                row = cursor.fetchone()
                return Listing.from_dict(dict(row)) if row else None
        
        return self.execute_with_retry(_get)
    
    def get_all(self) -> List[Listing]:
        """Получает все объявления."""
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listings ORDER BY price_rub")
                rows = cursor.fetchall()
                return [Listing.from_dict(dict(row)) for row in rows]
        
        return self.execute_with_retry(_get_all) or []
    
    def get_for_zakupka(self, reg_number: str) -> List[Listing]:
        """Получает все объявления для закупки."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM listings WHERE zakupka_reg_number = ? ORDER BY rank",
                    (reg_number,)
                )
                rows = cursor.fetchall()
                return [Listing.from_dict(dict(row)) for row in rows]
        
        return self.execute_with_retry(_get) or []
    
    def delete(self, id: str) -> bool:
        """Удаляет объявление по ID."""
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM listings WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_delete) or False
    
    def delete_for_zakupka(self, reg_number: str) -> int:
        """Удаляет все объявления для закупки."""
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM listings WHERE zakupka_reg_number = ?",
                    (reg_number,)
                )
                conn.commit()
                return cursor.rowcount
        
        return self.execute_with_retry(_delete) or 0
    
    def count(self) -> int:
        """Возвращает общее количество объявлений."""
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM listings")
                return cursor.fetchone()[0]
        
        return self.execute_with_retry(_count) or 0
