"""
Репозиторий для работы с закупками.
"""
from typing import Optional, List
from .base import BaseRepository
from models.zakupka import Zakupka


class ZakupkaRepository(BaseRepository[Zakupka]):
    """Репозиторий для CRUD операций с закупками."""
    
    def create_table(self) -> bool:
        """Создаёт таблицу zakupki."""
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS zakupki (
                        reg_number TEXT PRIMARY KEY,
                        description TEXT,
                        update_date TEXT,
                        bid_end_date TEXT,
                        initial_price REAL,
                        link TEXT,
                        combined_text TEXT,
                        two_gis_url TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                return True
        
        return self.execute_with_retry(_create) or False
    
    def save(self, zakupka: Zakupka) -> bool:
        """Сохраняет или обновляет закупку."""
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO zakupki
                    (reg_number, description, update_date, bid_end_date, initial_price, link, combined_text, two_gis_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    zakupka.reg_number,
                    zakupka.description,
                    zakupka.update_date,
                    zakupka.bid_end_date,
                    zakupka.initial_price,
                    zakupka.link,
                    zakupka.combined_text,
                    zakupka.two_gis_url
                ))
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_save) or False
    
    def get_by_id(self, reg_number: str) -> Optional[Zakupka]:
        """Получает закупку по номеру."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM zakupki WHERE reg_number = ?",
                    (reg_number,)
                )
                row = cursor.fetchone()
                return Zakupka.from_dict(dict(row)) if row else None
        
        return self.execute_with_retry(_get)
    
    def get_by_reg_numbers(self, reg_numbers: List[str]) -> List[Zakupka]:
        """Получает список закупок по списку номеров."""
        if not reg_numbers:
            return []
            
        def _get_many():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(reg_numbers))
                cursor.execute(
                    f"SELECT * FROM zakupki WHERE reg_number IN ({placeholders})",
                    reg_numbers
                )
                rows = cursor.fetchall()
                return [Zakupka.from_dict(dict(row)) for row in rows]
                
        return self.execute_with_retry(_get_many) or []

    def get_all(self) -> List[Zakupka]:
        """Получает все закупки."""
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupki")
                rows = cursor.fetchall()
                return [Zakupka.from_dict(dict(row)) for row in rows]
        
        return self.execute_with_retry(_get_all) or []
    
    def delete(self, reg_number: str) -> bool:
        """Удаляет закупку."""
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM zakupki WHERE reg_number = ?",
                    (reg_number,)
                )
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_delete) or False
    
    def update_two_gis_url(self, reg_number: str, url: str) -> bool:
        """Обновляет ссылку 2ГИС."""
        def _update():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE zakupki SET two_gis_url = ? WHERE reg_number = ?",
                    (url, reg_number)
                )
                conn.commit()
                # Принудительный checkpoint для WAL
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                
                rowcount = cursor.rowcount
                self.logger.debug(f"UPDATE rowcount={rowcount} for {reg_number}")
                
                # Проверяем что действительно сохранилось
                cursor.execute("SELECT two_gis_url FROM zakupki WHERE reg_number = ?", (reg_number,))
                row = cursor.fetchone()
                if row and row[0]:
                    self.logger.debug(f"Verified: URL saved for {reg_number}")
                    return True
                else:
                    self.logger.warning(f"NOT SAVED: {reg_number} - row={row}")
                    return False
        
        return self.execute_with_retry(_update) or False
    
    def get_with_two_gis_url(self) -> List[Zakupka]:
        """Получает закупки с заполненной ссылкой 2ГИС."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM zakupki WHERE two_gis_url IS NOT NULL AND two_gis_url != ''"
                )
                rows = cursor.fetchall()
                return [Zakupka.from_dict(dict(row)) for row in rows]
        
        return self.execute_with_retry(_get) or []
