"""
Репозиторий для работы с пользовательскими выборками.
"""
from typing import List
from .base import BaseRepository
from models.user_selection import UserSelection


class UserSelectionRepository(BaseRepository[UserSelection]):
    """Репозиторий для CRUD операций с пользовательскими выборками."""
    
    def create_table(self) -> bool:
        """Создаёт таблицу user_selections."""
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_selections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        reg_number TEXT NOT NULL,
                        selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number),
                        UNIQUE(user_id, reg_number)
                    )
                """)
                
                # Создаём индекс для быстрого поиска
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_selections_user_id 
                    ON user_selections(user_id)
                """)
                
                conn.commit()
                return True
        
        return self.execute_with_retry(_create) or False
    
    def add_selection(self, user_id: int, reg_number: str) -> bool:
        """Добавляет закупку в выборку пользователя."""
        def _add():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO user_selections (user_id, reg_number)
                        VALUES (?, ?)
                    """, (user_id, reg_number))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    # Игнорируем дубликаты (UNIQUE constraint)
                    return False
        
        return self.execute_with_retry(_add) or False
    
    def remove_selection(self, user_id: int, reg_number: str) -> bool:
        """Удаляет закупку из выборки пользователя."""
        def _remove():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM user_selections 
                    WHERE user_id = ? AND reg_number = ?
                """, (user_id, reg_number))
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_remove) or False
    
    def get_user_selections(self, user_id: int) -> List[str]:
        """Получает список reg_numbers выбранных пользователем закупок."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT reg_number FROM user_selections 
                    WHERE user_id = ?
                    ORDER BY selected_at DESC
                """, (user_id,))
                rows = cursor.fetchall()
                return [row['reg_number'] for row in rows]
        
        return self.execute_with_retry(_get) or []
    
    def clear_user_selections(self, user_id: int) -> bool:
        """Удаляет все выборки пользователя."""
        def _clear():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM user_selections WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                return True
        
        return self.execute_with_retry(_clear) or False
    
    def get_selection_count(self, user_id: int) -> int:
        """Возвращает количество выбранных закупок."""
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM user_selections 
                    WHERE user_id = ?
                """, (user_id,))
                row = cursor.fetchone()
                return row['cnt'] if row else 0
        
        return self.execute_with_retry(_count) or 0
    
    # Реализация абстрактных методов BaseRepository
    
    def save(self, selection: UserSelection) -> bool:
        """Сохраняет выборку (используется add_selection)."""
        return self.add_selection(selection.user_id, selection.reg_number)
    
    def get_by_id(self, selection_id: int) -> UserSelection:
        """Получает выборку по ID."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM user_selections WHERE id = ?
                """, (selection_id,))
                row = cursor.fetchone()
                return UserSelection.from_row(row) if row else None
        
        return self.execute_with_retry(_get)
    
    def get_all(self) -> List[UserSelection]:
        """Получает все выборки."""
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_selections ORDER BY selected_at DESC")
                rows = cursor.fetchall()
                return [UserSelection.from_row(row) for row in rows]
        
        return self.execute_with_retry(_get) or []
    
    def delete(self, selection_id: int) -> bool:
        """Удаляет выборку по ID."""
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_selections WHERE id = ?", (selection_id,))
                conn.commit()
                return cursor.rowcount > 0
        
        return self.execute_with_retry(_delete) or False

