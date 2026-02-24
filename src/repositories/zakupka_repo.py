"""Repository for purchases (zakupki)."""

from typing import List, Optional

from models.zakupka import Zakupka

from .base import BaseRepository


class ZakupkaRepository(BaseRepository[Zakupka]):
    """CRUD operations for zakupki."""

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS zakupki (
                        reg_number TEXT PRIMARY KEY,
                        description TEXT,
                        update_date TEXT,
                        bid_end_date TEXT,
                        initial_price REAL,
                        link TEXT,
                        combined_text TEXT,
                        two_gis_url TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'raw',
                        prepared_by_user_id INTEGER,
                        prepared_at TIMESTAMP
                    )
                    """
                )
                conn.commit()
                return True

        return self.execute_with_retry(_create) or False

    def save(self, zakupka: Zakupka) -> bool:
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                prepared_at_str = zakupka.prepared_at.isoformat() if zakupka.prepared_at else None

                sql = self.build_upsert_sql(
                    table="zakupki",
                    insert_columns=[
                        "reg_number",
                        "description",
                        "update_date",
                        "bid_end_date",
                        "initial_price",
                        "link",
                        "combined_text",
                        "two_gis_url",
                        "status",
                        "prepared_by_user_id",
                        "prepared_at",
                    ],
                    conflict_columns=["reg_number"],
                )
                cursor.execute(
                    sql,
                    (
                        zakupka.reg_number,
                        zakupka.description,
                        zakupka.update_date,
                        zakupka.bid_end_date,
                        zakupka.initial_price,
                        zakupka.link,
                        zakupka.combined_text,
                        zakupka.two_gis_url,
                        zakupka.status,
                        zakupka.prepared_by_user_id,
                        prepared_at_str,
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_save) or False

    def get_by_id(self, reg_number: str) -> Optional[Zakupka]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupki WHERE reg_number = ?", (reg_number,))
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                return Zakupka.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_by_reg_numbers(self, reg_numbers: List[str]) -> List[Zakupka]:
        if not reg_numbers:
            return []

        def _get_many():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(reg_numbers))
                cursor.execute(
                    f"SELECT * FROM zakupki WHERE reg_number IN ({placeholders})",
                    reg_numbers,
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_many) or []

    def get_all(self) -> List[Zakupka]:
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupki")
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_all) or []

    def delete(self, reg_number: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM zakupki WHERE reg_number = ?", (reg_number,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False

    def update_two_gis_url(self, reg_number: str, url: str) -> bool:
        def _update():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE zakupki SET two_gis_url = ? WHERE reg_number = ?",
                    (url, reg_number),
                )
                conn.commit()

                # WAL checkpoint is SQLite-only.
                if not self.is_postgres:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

                cursor.execute("SELECT two_gis_url FROM zakupki WHERE reg_number = ?", (reg_number,))
                row = cursor.fetchone()
                if not row:
                    self.logger.warning("No zakupka row found for %s", reg_number)
                    return False

                saved_url = row[0] if not hasattr(row, "keys") else row["two_gis_url"]
                if saved_url:
                    self.logger.debug("Verified: URL saved for %s", reg_number)
                    return True

                self.logger.warning("URL was not saved for %s", reg_number)
                return False

        return self.execute_with_retry(_update) or False

    def get_with_two_gis_url(self) -> List[Zakupka]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM zakupki WHERE two_gis_url IS NOT NULL AND two_gis_url != ''"
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get) or []

    def update_status(
        self,
        reg_number: str,
        status: str,
        prepared_by_user_id: Optional[int] = None,
    ) -> bool:
        def _update():
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if status == "url_ready":
                    from datetime import datetime

                    cursor.execute(
                        "UPDATE zakupki SET status = ?, prepared_by_user_id = ?, prepared_at = ? WHERE reg_number = ?",
                        (status, prepared_by_user_id, datetime.now().isoformat(), reg_number),
                    )
                else:
                    cursor.execute(
                        "UPDATE zakupki SET status = ? WHERE reg_number = ?",
                        (status, reg_number),
                    )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_update) or False

    def get_by_status(self, status: str) -> List[Zakupka]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupki WHERE status = ?", (status,))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get) or []

    def get_by_statuses(self, statuses: List[str]) -> List[Zakupka]:
        if not statuses:
            return []

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(statuses))
                cursor.execute(
                    f"SELECT * FROM zakupki WHERE status IN ({placeholders})",
                    statuses,
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get) or []

    def get_status_counts(self) -> dict:
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM zakupki
                    GROUP BY status
                    """
                )
                rows = cursor.fetchall()
                return {row["status"]: row["count"] for row in rows}

        return self.execute_with_retry(_count) or {}
