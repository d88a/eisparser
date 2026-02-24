"""Repository for user selections."""

from typing import List

from models.user_selection import UserSelection

from .base import BaseRepository


class UserSelectionRepository(BaseRepository[UserSelection]):
    """CRUD for user selection queue."""

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS user_selections (
                        id {id_sql},
                        user_id INTEGER NOT NULL,
                        reg_number TEXT NOT NULL,
                        selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number),
                        UNIQUE(user_id, reg_number)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_selections_user_id ON user_selections(user_id)"
                )
                conn.commit()
                return True

        return self.execute_with_retry(_create) or False

    def add_selection(self, user_id: int, reg_number: str) -> bool:
        def _add():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_selections (user_id, reg_number)
                    VALUES (?, ?)
                    ON CONFLICT (user_id, reg_number) DO NOTHING
                    """,
                    (user_id, reg_number),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_add) or False

    def remove_selection(self, user_id: int, reg_number: str) -> bool:
        def _remove():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_selections WHERE user_id = ? AND reg_number = ?",
                    (user_id, reg_number),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_remove) or False

    def get_user_selections(self, user_id: int) -> List[str]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT reg_number FROM user_selections
                    WHERE user_id = ?
                    ORDER BY selected_at DESC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                return [row["reg_number"] for row in rows]

        return self.execute_with_retry(_get) or []

    def clear_user_selections(self, user_id: int) -> bool:
        def _clear():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_selections WHERE user_id = ?", (user_id,))
                conn.commit()
                return True

        return self.execute_with_retry(_clear) or False

    def get_selection_count(self, user_id: int) -> int:
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM user_selections WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                return row["cnt"] if row else 0

        return self.execute_with_retry(_count) or 0

    def save(self, selection: UserSelection) -> bool:
        return self.add_selection(selection.user_id, selection.reg_number)

    def get_by_id(self, selection_id: int) -> UserSelection:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_selections WHERE id = ?", (selection_id,))
                row = cursor.fetchone()
                return UserSelection.from_row(row) if row else None

        return self.execute_with_retry(_get)

    def get_all(self) -> List[UserSelection]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_selections ORDER BY selected_at DESC")
                rows = cursor.fetchall()
                return [UserSelection.from_row(row) for row in rows]

        return self.execute_with_retry(_get) or []

    def delete(self, selection_id: int) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_selections WHERE id = ?", (selection_id,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False
