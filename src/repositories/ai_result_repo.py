"""
Репозиторий для результатов ИИ-анализа.
"""
from typing import Optional, List
from .base import BaseRepository
from models.ai_result import AIResult


class AIResultRepository(BaseRepository[AIResult]):
    """Репозиторий для CRUD операций с результатами ИИ."""
    
    def create_table(self) -> bool:
        """Создаёт таблицу ai_results."""
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_results (
                        reg_number TEXT PRIMARY KEY,
                        zakupka_name TEXT,
                        address TEXT,
                        city TEXT,
                        area_min_m2 REAL,
                        area_max_m2 REAL,
                        rooms TEXT,
                        rooms_parsed TEXT,
                        floor TEXT,
                        building_floors_min TEXT,
                        year_build_str TEXT,
                        wear_percent REAL,
                        zakazchik TEXT,
                        FOREIGN KEY (reg_number) REFERENCES zakupki (reg_number)
                    )
                """)
                conn.commit()
                return True
        
        return self.execute_with_retry(_create) or False
    
    def save(self, result: AIResult) -> bool:
        """Сохраняет или обновляет результат ИИ."""
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO ai_results
                    (reg_number, zakupka_name, address, city,
                     area_min_m2, area_max_m2, rooms, rooms_parsed,
                     floor, building_floors_min, year_build_str, wear_percent,
                     zakazchik)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.reg_number, result.zakupka_name, result.address,
                    result.city,
                    result.area_min_m2, result.area_max_m2, result.rooms,
                    result.rooms_parsed, result.floor, result.building_floors_min,
                    result.year_build_str, result.wear_percent, result.zakazchik
                ))
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_save) or False
    
    def get_by_id(self, reg_number: str) -> Optional[AIResult]:
        """Получает результат по номеру закупки."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM ai_results WHERE reg_number = ?",
                    (reg_number,)
                )
                row = cursor.fetchone()
                return AIResult.from_dict(dict(row)) if row else None
        
        return self.execute_with_retry(_get)
    
    def get_all(self) -> List[AIResult]:
        """Получает все результаты ИИ, отсортированные по дате (свежие первые)."""
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ai_results ORDER BY rowid DESC")
                rows = cursor.fetchall()
                return [AIResult.from_dict(dict(row)) for row in rows]
        
        return self.execute_with_retry(_get_all) or []
    
    def delete(self, reg_number: str) -> bool:
        """Удаляет результат."""
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM ai_results WHERE reg_number = ?",
                    (reg_number,)
                )
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_delete) or False
    
    def update_rooms_parsed(self, reg_number: str, rooms_parsed: str) -> bool:
        """Обновляет распарсенные комнаты."""
        def _update():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE ai_results SET rooms_parsed = ? WHERE reg_number = ?",
                    (rooms_parsed, reg_number)
                )
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_update) or False
