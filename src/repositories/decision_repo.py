"""Repository for user decisions."""

from typing import List, Optional

from models.decision import Decision
from repositories.base import BaseRepository


class DecisionRepository(BaseRepository[Decision]):
    """CRUD operations for decisions."""

    def create_table(self) -> bool:
        id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        sql = f"""
        CREATE TABLE IF NOT EXISTS decisions (
            id {id_sql},
            user_id INTEGER NOT NULL,
            reg_number TEXT NOT NULL,
            stage INTEGER NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected', 'skipped', 'selected')),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
        try:
            with self.get_connection() as conn:
                conn.execute(sql)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_user_stage ON decisions(user_id, stage)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_reg_user ON decisions(reg_number, user_id)")
                conn.commit()
            self.logger.info("decisions table is ready")
            return True
        except Exception as exc:
            self.logger.error("Failed to create decisions table: %s", exc)
            return False

    def save(self, decision: Decision) -> bool:
        base_sql = (
            "INSERT INTO decisions (user_id, reg_number, stage, decision, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        sql = f"{base_sql} RETURNING id" if self.is_postgres else base_sql

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        decision.user_id,
                        decision.reg_number,
                        decision.stage,
                        decision.decision,
                        decision.comment,
                        decision.created_at.isoformat(),
                    ),
                )
                if self.is_postgres:
                    row = cursor.fetchone()
                    decision.id = row[0] if row else None
                else:
                    decision.id = cursor.lastrowid
                conn.commit()
            self.logger.info("Decision saved id=%s", decision.id)
            return True
        except Exception as exc:
            self.logger.error("Failed to save decision: %s", exc)
            return False

    def get_by_id(self, id: int) -> Optional[Decision]:
        sql = "SELECT * FROM decisions WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return Decision.from_row(row)
        except Exception as exc:
            self.logger.error("Failed to get decision id=%s: %s", id, exc)
        return None

    def get_all(self) -> List[Decision]:
        sql = "SELECT * FROM decisions"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [Decision.from_row(row) for row in rows]
        except Exception as exc:
            self.logger.error("Failed to get decisions: %s", exc)
            return []

    def delete(self, id: int) -> bool:
        sql = "DELETE FROM decisions WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            return True
        except Exception as exc:
            self.logger.error("Failed to delete decision id=%s: %s", id, exc)
            return False

    def get_last_decision(self, user_id: int, reg_number: str, stage: int) -> Optional[Decision]:
        sql = """
        SELECT * FROM decisions
        WHERE user_id = ? AND reg_number = ? AND stage = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (user_id, reg_number, stage)).fetchone()
                if row:
                    return Decision.from_row(row)
        except Exception as exc:
            self.logger.error("Failed to get last decision: %s", exc)
        return None

    def get_approved_reg_numbers(self, user_id: int, stage: int) -> List[str]:
        sql = """
        SELECT d.reg_number
        FROM decisions d
        JOIN (
            SELECT reg_number, MAX(id) AS max_id
            FROM decisions
            WHERE user_id = ? AND stage = ?
            GROUP BY reg_number
        ) latest
          ON d.reg_number = latest.reg_number
         AND d.id = latest.max_id
        WHERE d.user_id = ? AND d.stage = ? AND d.decision = 'approved'
        """
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (user_id, stage, user_id, stage)).fetchall()
                return [row["reg_number"] for row in rows]
        except Exception as exc:
            self.logger.error("Failed to get approved decisions: %s", exc)
            return []

    def delete_by_decision_value(self, decision_value: str) -> int:
        sql = "DELETE FROM decisions WHERE decision = ?"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, (decision_value,))
                conn.commit()
                return cursor.rowcount or 0
        except Exception as exc:
            self.logger.error("Failed to delete decisions '%s': %s", decision_value, exc)
            return 0

    def get_selected_reg_numbers(self, user_id: int, stage: int) -> List[str]:
        sql = """
        SELECT d.reg_number
        FROM decisions d
        JOIN (
            SELECT reg_number, MAX(id) AS max_id
            FROM decisions
            WHERE user_id = ? AND stage = ?
            GROUP BY reg_number
        ) latest
          ON d.reg_number = latest.reg_number
         AND d.id = latest.max_id
        WHERE d.user_id = ? AND d.stage = ? AND d.decision = 'selected'
        """
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (user_id, stage, user_id, stage)).fetchall()
                return [row["reg_number"] for row in rows]
        except Exception as exc:
            self.logger.error("Failed to get selected decisions: %s", exc)
            return []
