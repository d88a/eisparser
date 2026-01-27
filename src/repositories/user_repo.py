"""
Репозиторий пользователей.
"""
from typing import Optional, List
from repositories.base import BaseRepository
from models.user import User


class UserRepository(BaseRepository[User]):
    """
    Репозиторий для работы с таблицей users.
    """
    
    def create_table(self) -> bool:
        """Создаёт таблицу users."""
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql)
                conn.commit()
            self.logger.info("Таблица users создана/проверена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка создания таблицы users: {e}")
            return False
    
    def save(self, user: User) -> bool:
        """
        Сохраняет пользователя в БД.
        
        Args:
            user: Объект User
            
        Returns:
            True если успешно
        """
        sql = """
        INSERT INTO users (email, role, created_at)
        VALUES (?, ?, ?)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (user.email, user.role, user.created_at.isoformat())
                )
                conn.commit()
                user.id = cursor.lastrowid
            self.logger.info(f"Пользователь {user.email} сохранён с id={user.id}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения пользователя {user.email}: {e}")
            return False
    
    def get_by_id(self, id: int) -> Optional[User]:
        """
        Получает пользователя по ID.
        
        Args:
            id: ID пользователя
            
        Returns:
            User или None
        """
        sql = "SELECT * FROM users WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return User.from_row(row)
        except Exception as e:
            self.logger.error(f"Ошибка получения пользователя id={id}: {e}")
        return None
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Получает пользователя по email.
        
        Args:
            email: Email пользователя
            
        Returns:
            User или None
        """
        sql = "SELECT * FROM users WHERE email = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (email,)).fetchone()
                if row:
                    return User.from_row(row)
        except Exception as e:
            self.logger.error(f"Ошибка получения пользователя email={email}: {e}")
        return None
    
    def get_all(self) -> List[User]:
        """Получает всех пользователей."""
        sql = "SELECT * FROM users ORDER BY created_at DESC"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [User.from_row(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Ошибка получения пользователей: {e}")
            return []
    
    def delete(self, id: int) -> bool:
        """
        Удаляет пользователя по ID.
        
        Args:
            id: ID пользователя
            
        Returns:
            True если успешно
        """
        sql = "DELETE FROM users WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            self.logger.info(f"Пользователь id={id} удалён")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления пользователя id={id}: {e}")
            return False
    
    def count(self) -> int:
        """Возвращает количество пользователей."""
        sql = "SELECT COUNT(*) FROM users"
        try:
            with self.get_connection() as conn:
                result = conn.execute(sql).fetchone()
                return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"Ошибка подсчёта пользователей: {e}")
            return 0
