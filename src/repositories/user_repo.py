"""Repository for users."""

from typing import List, Optional

from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """CRUD operations for users table."""

    def create_table(self) -> bool:
        id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        sql = f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_sql},
            email TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            display_name TEXT,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql)
                # Backward-compatible migration for existing databases.
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
                except Exception:
                    pass
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
                conn.commit()
            self.logger.info("users table is ready")
            return True
        except Exception as exc:
            try:
                with self.get_connection() as conn:
                    conn.execute(sql)
                    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
                    conn.commit()
                self.logger.info("users table is ready")
                return True
            except Exception as inner_exc:
                self.logger.error("Failed to create users table: %s", inner_exc)
                return False

    def save(self, user: User) -> bool:
        base_sql = "INSERT INTO users (email, role, display_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)"
        sql = f"{base_sql} RETURNING id" if self.is_postgres else base_sql
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (user.email, user.role, user.display_name, user.password_hash, user.created_at.isoformat()),
                )
                if self.is_postgres:
                    row = cursor.fetchone()
                    user.id = row[0] if row else None
                else:
                    user.id = cursor.lastrowid
                conn.commit()
            self.logger.info("User saved: %s id=%s", user.email, user.id)
            return True
        except Exception as exc:
            self.logger.error("Failed to save user %s: %s", user.email, exc)
            return False

    def get_by_id(self, id: int) -> Optional[User]:
        sql = "SELECT * FROM users WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return User.from_row(row)
        except Exception as exc:
            self.logger.error("Failed to get user id=%s: %s", id, exc)
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        sql = "SELECT * FROM users WHERE email = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (email,)).fetchone()
                if row:
                    return User.from_row(row)
        except Exception as exc:
            self.logger.error("Failed to get user email=%s: %s", email, exc)
        return None

    def create_public_user(self, email: str, password_hash: str) -> Optional[User]:
        normalized_email = (email or "").strip().lower()
        if not normalized_email or not password_hash:
            return None
        if self.get_by_email(normalized_email):
            return None
        default_name = normalized_email.split("@", 1)[0].strip() or normalized_email
        user = User(email=normalized_email, role="public", display_name=default_name, password_hash=password_hash)
        if not self.save(user):
            return None
        return user

    def update_display_name(self, email: str, display_name: str) -> bool:
        normalized_email = (email or "").strip().lower()
        clean_name = " ".join((display_name or "").strip().split())
        if not normalized_email:
            return False
        try:
            with self.get_connection() as conn:
                cur = conn.execute(
                    "UPDATE users SET display_name = ? WHERE LOWER(email) = ?",
                    (clean_name, normalized_email),
                )
                conn.commit()
                return bool(cur.rowcount and int(cur.rowcount) > 0)
        except Exception as exc:
            self.logger.error("Failed to update display_name for %s: %s", normalized_email, exc)
            return False

    def update_password_hash(self, email: str, password_hash: str) -> bool:
        normalized_email = (email or "").strip().lower()
        if not normalized_email or not password_hash:
            return False
        try:
            with self.get_connection() as conn:
                cur = conn.execute(
                    "UPDATE users SET password_hash = ? WHERE LOWER(email) = ?",
                    (password_hash, normalized_email),
                )
                conn.commit()
                return bool(cur.rowcount and int(cur.rowcount) > 0)
        except Exception as exc:
            self.logger.error("Failed to update password hash for %s: %s", normalized_email, exc)
            return False

    def get_all(self) -> List[User]:
        sql = "SELECT * FROM users ORDER BY created_at DESC"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [User.from_row(row) for row in rows]
        except Exception as exc:
            self.logger.error("Failed to get users: %s", exc)
            return []

    def delete(self, id: int) -> bool:
        sql = "DELETE FROM users WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            self.logger.info("User deleted id=%s", id)
            return True
        except Exception as exc:
            self.logger.error("Failed to delete user id=%s: %s", id, exc)
            return False

    def count(self) -> int:
        sql = "SELECT COUNT(*) FROM users"
        try:
            with self.get_connection() as conn:
                result = conn.execute(sql).fetchone()
                return result[0] if result else 0
        except Exception as exc:
            self.logger.error("Failed to count users: %s", exc)
            return 0
