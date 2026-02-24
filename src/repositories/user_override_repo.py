"""Repository for user overrides."""

from typing import Dict, List, Optional

from models.user_override import UserOverride
from repositories.base import BaseRepository


class UserOverrideRepository(BaseRepository[UserOverride]):
    """CRUD operations for user overrides."""

    def create_table(self) -> bool:
        id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        sql = f"""
        CREATE TABLE IF NOT EXISTS user_overrides (
            id {id_sql},
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
            self.logger.info("user_overrides table is ready")
            return True
        except Exception as exc:
            self.logger.error("Failed to create user_overrides table: %s", exc)
            return False

    def save(self, override: UserOverride) -> bool:
        sql = self.build_upsert_sql(
            table="user_overrides",
            insert_columns=["user_id", "reg_number", "field_name", "value", "created_at"],
            conflict_columns=["user_id", "reg_number", "field_name"],
            update_columns=["value", "created_at"],
        )
        try:
            with self.get_connection() as conn:
                conn.execute(
                    sql,
                    (
                        override.user_id,
                        override.reg_number,
                        override.field_name,
                        override.value,
                        override.created_at.isoformat(),
                    ),
                )
                conn.commit()
            self.logger.info("Override saved: %s.%s", override.reg_number, override.field_name)
            return True
        except Exception as exc:
            self.logger.error("Failed to save override: %s", exc)
            return False

    def get_by_id(self, id: int) -> Optional[UserOverride]:
        sql = "SELECT * FROM user_overrides WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return UserOverride.from_row(row)
        except Exception as exc:
            self.logger.error("Failed to get override id=%s: %s", id, exc)
        return None

    def get_all(self) -> List[UserOverride]:
        sql = "SELECT * FROM user_overrides"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [UserOverride.from_row(row) for row in rows]
        except Exception as exc:
            self.logger.error("Failed to get overrides: %s", exc)
            return []

    def delete(self, id: int) -> bool:
        sql = "DELETE FROM user_overrides WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            return True
        except Exception as exc:
            self.logger.error("Failed to delete override id=%s: %s", id, exc)
            return False

    def get_for_zakupka(self, reg_number: str, user_id: int = 1) -> Dict[str, str]:
        sql = "SELECT field_name, value FROM user_overrides WHERE reg_number = ? AND user_id = ?"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (reg_number, user_id)).fetchall()
                return {row["field_name"]: row["value"] for row in rows}
        except Exception as exc:
            self.logger.error("Failed to get overrides for %s: %s", reg_number, exc)
            return {}

    def get_effective_value(self, reg_number: str, field_name: str, ai_value, user_id: int = 1):
        overrides = self.get_for_zakupka(reg_number, user_id)
        return overrides.get(field_name, ai_value)
