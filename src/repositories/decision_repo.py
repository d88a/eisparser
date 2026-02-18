"""
Репозиторий решений пользователей.
"""
from typing import Optional, List
from repositories.base import BaseRepository
from models.decision import Decision


class DecisionRepository(BaseRepository[Decision]):
    """
    Репозиторий для работы с таблицей decisions.
    """
    
    def create_table(self) -> bool:
        """Создаёт таблицу decisions."""
        sql = """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                # Индексы для быстрого поиска
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_user_stage ON decisions(user_id, stage)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_reg_user ON decisions(reg_number, user_id)")
                conn.commit()
            self.logger.info("Таблица decisions создана/проверена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка создания таблицы decisions: {e}")
            return False
            
    def save(self, decision: Decision) -> bool:
        """
        Сохраняет решение в БД.
        Новая запись = новое решение.
        """
        sql = """
        INSERT INTO decisions (user_id, reg_number, stage, decision, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
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
                        decision.created_at.isoformat()
                    )
                )
                conn.commit()
                decision.id = cursor.lastrowid
            self.logger.info(f"Решение id={decision.id} сохранено")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения решения: {e}")
            return False

    def get_by_id(self, id: int) -> Optional[Decision]:
        """Получает решение по ID."""
        sql = "SELECT * FROM decisions WHERE id = ?"
        try:
            with self.get_connection() as conn:
                row = conn.execute(sql, (id,)).fetchone()
                if row:
                    return Decision.from_row(row)
        except Exception as e:
            self.logger.error(f"Ошибка получения решения id={id}: {e}")
        return None

    def get_all(self) -> List[Decision]:
        """Получает все решения."""
        sql = "SELECT * FROM decisions"
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [Decision.from_row(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Ошибка получения всех решений: {e}")
            return []

    def delete(self, id: int) -> bool:
        """Удаляет решение по ID."""
        sql = "DELETE FROM decisions WHERE id = ?"
        try:
            with self.get_connection() as conn:
                conn.execute(sql, (id,))
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления решения id={id}: {e}")
            return False

    def get_last_decision(self, user_id: int, reg_number: str, stage: int) -> Optional[Decision]:
        """
        Получает последнее решение пользователя по конкретной закупке на этапе.
        """
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
        except Exception as e:
            self.logger.error(f"Ошибка получения последнего решения: {e}")
        return None

    def get_approved_reg_numbers(self, user_id: int, stage: int) -> List[str]:
        """Returns reg_number values whose latest decision is approved for the stage."""
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
        except Exception as e:
            self.logger.error(f"Error fetching approved decisions: {e}")
            return []

    def delete_by_decision_value(self, decision_value: str) -> int:
        """Deletes all decisions with the given decision value."""
        sql = "DELETE FROM decisions WHERE decision = ?"
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(sql, (decision_value,))
                conn.commit()
                return cursor.rowcount or 0
        except Exception as e:
            self.logger.error(f"Error deleting decisions '{decision_value}': {e}")
            return 0

    def get_selected_reg_numbers(self, user_id: int, stage: int) -> List[str]:
        """Returns reg_number values whose latest decision is selected for the stage."""
        sql = """
        SELECT reg_number
        FROM (
            SELECT reg_number, decision, MAX(created_at) as last_date
            FROM decisions
            WHERE user_id = ? AND stage = ?
            GROUP BY reg_number
        )
        WHERE decision = 'selected'
        """
        try:
            with self.get_connection() as conn:
                rows = conn.execute(sql, (user_id, stage)).fetchall()
                return [row["reg_number"] for row in rows]
        except Exception as e:
            self.logger.error(f"Error fetching selected decisions: {e}")
            return []
