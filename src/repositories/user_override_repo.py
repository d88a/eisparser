"""
Репозиторий для пользовательских переопределений.
"""
from typing import Optional, List, Dict
from repositories.base import BaseRepository
from models.user_override import UserOverride


class UserOverrideRepository(BaseRepository[UserOverride]):
    """Репозиторий для CRUD операций с user_overrides."""
    
    def create_table(self) -> bool:
        """Создаёт таблицу user_overrides."""
        sql = """
        CREATE TABLE IF NOT EXISTS user_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reg_number TEXT NOT NULL,
            field_name TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, reg_number, field_name)
        )
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_overrides_reg ON user_overrides(reg_number)")
                conn.commit()
            self.logger.info("Таблица user_overrides создана/проверена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка создания таблицы user_overrides: {e}")
            return False
    
    def save(self, override: UserOverride) -> bool:
        """Сохраняет или обновляет override (upsert)."""
        sql = """
        INSERT OR REPLACE INTO user_overrides (user_id, reg_number, field_name, value, created_at)
        VALUES (?, ?, ?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (
                    override.user_id,
                    override.reg_number,
                    override.field_name,
                    override.value,
                    override.created_at.isoformat()
                ))
                conn.commit()
            self.logger.info(f"Override сохранён: {override.reg_number}.{override.field_name}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения override: {e}")
            return False
    
    def get_by_id(self, id: int) -> Optional[UserOverride]:
        """Получает override по ID."""
        sql = "SELECT * FROM user_overrides WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return UserOverride.from_row(row)
        except Exception as e:
            self.logger.error(f"Ошибка получения override: {e}")
        return None
    
    def get_all(self) -> List[UserOverride]:
        """Получает все overrides."""
        sql = "SELECT * FROM user_overrides"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [UserOverride.from_row(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Ошибка получения overrides: {e}")
            return []
    
    def delete(self, id: int) -> bool:
        """Удаляет override."""
        sql = "DELETE FROM user_overrides WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления override: {e}")
            return False
    
    def get_for_zakupka(self, reg_number: str, user_id: int = 1) -> Dict[str, str]:
        """
        Возвращает все overrides для закупки как словарь {field_name: value}.
        """
        sql = "SELECT field_name, value FROM user_overrides WHERE reg_number = ? AND user_id = ?"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (reg_number, user_id)).fetchall()
                return {row['field_name']: row['value'] for row in rows}
        except Exception as e:
            self.logger.error(f"Ошибка получения overrides для {reg_number}: {e}")
            return {}
    
    def get_effective_value(self, reg_number: str, field_name: str, ai_value, user_id: int = 1):
        """
        Возвращает effective_value = override ?? ai_value.
        """
        overrides = self.get_for_zakupka(reg_number, user_id)
        return overrides.get(field_name, ai_value)
