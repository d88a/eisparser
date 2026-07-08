"""Repository for purchases (zakupki)."""

from datetime import datetime
from typing import List, Optional

from models.statuses import ZakupkaStatus
from models.zakupka import Zakupka

from .base import BaseRepository


class ZakupkaRepository(BaseRepository[Zakupka]):
    """CRUD operations for zakupki."""

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                default_status = ZakupkaStatus.RAW
                cursor.execute(
                    f"""
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
                        status TEXT DEFAULT '{default_status}',
                        prepared_by_user_id INTEGER,
                        prepared_at TIMESTAMP
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_zakupki_status ON zakupki(status)")
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
                now_iso = datetime.now().isoformat()

                if status == ZakupkaStatus.URL_READY:
                    cursor.execute(
                        "UPDATE zakupki SET status = ?, processed_at = ?, prepared_by_user_id = ?, prepared_at = ? WHERE reg_number = ?",
                        (status, now_iso, prepared_by_user_id, now_iso, reg_number),
                    )
                else:
                    cursor.execute(
                        "UPDATE zakupki SET status = ?, processed_at = ? WHERE reg_number = ?",
                        (status, now_iso, reg_number),
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

    def get_by_statuses_limited_ordered(self, statuses: List[str], limit: int) -> List[Zakupka]:
        if not statuses:
            return []
        safe_limit = max(1, int(limit))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(statuses))
                cursor.execute(
                    f"""
                    SELECT * FROM zakupki
                    WHERE status IN ({placeholders})
                    ORDER BY
                        CASE WHEN prepared_at IS NULL THEN 1 ELSE 0 END,
                        prepared_at DESC,
                        CASE WHEN processed_at IS NULL THEN 1 ELSE 0 END,
                        processed_at DESC,
                        update_date DESC
                    LIMIT ?
                    """,
                    statuses + [safe_limit],
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Zakupka.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get) or []

    def get_public_list_page(self, statuses: List[str], offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        if not statuses:
            return [], 0

        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(statuses))
                cursor.execute(
                    f"SELECT COUNT(*) AS c FROM zakupki WHERE status IN ({placeholders})",
                    statuses,
                )
                count_row = cursor.fetchone()
                total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

                cursor.execute(
                    f"""
                    SELECT
                        reg_number,
                        description,
                        update_date,
                        bid_end_date,
                        initial_price,
                        status,
                        prepared_at,
                        processed_at
                    FROM zakupki
                    WHERE status IN ({placeholders})
                    ORDER BY
                        CASE WHEN prepared_at IS NULL THEN 1 ELSE 0 END,
                        prepared_at DESC,
                        CASE WHEN processed_at IS NULL THEN 1 ELSE 0 END,
                        processed_at DESC,
                        update_date DESC
                    LIMIT ? OFFSET ?
                    """,
                    statuses + [safe_limit, safe_offset],
                )
                rows = cursor.fetchall()
                items = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        items.append(row_dict)
                return items, total

        result = self.execute_with_retry(_get)
        return result if result is not None else ([], 0)

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

    def get_admin_all_page(self, offset: int = 0, limit: int = 20) -> tuple[List[Zakupka], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) AS c FROM zakupki")
                count_row = cursor.fetchone()
                total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

                cursor.execute(
                    """
                    SELECT *
                    FROM zakupki
                    ORDER BY
                        CASE WHEN processed_at IS NULL THEN 1 ELSE 0 END,
                        processed_at DESC,
                        update_date DESC
                    LIMIT ? OFFSET ?
                    """,
                    (safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
                items: List[Zakupka] = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        items.append(Zakupka.from_dict(row_dict))
                return items, total

        result = self.execute_with_retry(_get)
        return result if result is not None else ([], 0)

    def get_stage4_page_with_ai_city(
        self,
        statuses: List[str],
        offset: int = 0,
        limit: int = 20,
        processed_view: bool = False,
    ) -> tuple[list[dict], int]:
        if not statuses:
            return [], 0

        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(statuses))
                cursor.execute(
                    f"SELECT COUNT(*) AS c FROM zakupki WHERE status IN ({placeholders})",
                    statuses,
                )
                count_row = cursor.fetchone()
                total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

                if processed_view:
                    order_sql = """
                        ORDER BY
                            CASE WHEN z.processed_at IS NULL THEN 1 ELSE 0 END,
                            z.processed_at DESC,
                            CASE WHEN z.prepared_at IS NULL THEN 1 ELSE 0 END,
                            z.prepared_at DESC,
                            z.update_date DESC
                    """
                else:
                    order_sql = """
                        ORDER BY
                            CASE WHEN z.prepared_at IS NULL THEN 1 ELSE 0 END,
                            z.prepared_at DESC,
                            CASE WHEN z.processed_at IS NULL THEN 1 ELSE 0 END,
                            z.processed_at DESC,
                            z.update_date DESC
                    """

                cursor.execute(
                    f"""
                    SELECT
                        z.reg_number,
                        z.description,
                        z.update_date,
                        z.bid_end_date,
                        z.initial_price,
                        z.link,
                        z.two_gis_url,
                        z.status,
                        a.city AS ai_city
                    FROM zakupki z
                    LEFT JOIN ai_results a ON a.reg_number = z.reg_number
                    WHERE z.status IN ({placeholders})
                    {order_sql}
                    LIMIT ? OFFSET ?
                    """,
                    statuses + [safe_limit, safe_offset],
                )
                rows = cursor.fetchall()
                items = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        items.append(row_dict)
                return items, total

        result = self.execute_with_retry(_get)
        return result if result is not None else ([], 0)

    def get_stage2_processed_page(self, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM zakupki z
                    INNER JOIN ai_results a ON a.reg_number = z.reg_number
                    WHERE z.processed_at IS NOT NULL
                    """
                )
                count_row = cursor.fetchone()
                total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

                cursor.execute(
                    """
                    SELECT
                        z.reg_number,
                        z.description,
                        z.update_date,
                        z.bid_end_date,
                        z.initial_price,
                        z.processed_at,
                        z.status,
                        a.city AS ai_city,
                        a.area_min_m2 AS ai_area_min,
                        a.area_max_m2 AS ai_area_max,
                        a.zakupka_name AS ai_zakupka_name,
                        a.address AS ai_address,
                        a.rooms AS ai_rooms,
                        a.floor AS ai_floor,
                        a.building_floors_min AS ai_building_floors_min,
                        a.year_build_str AS ai_year_build,
                        a.wear_percent AS ai_wear_percent,
                        a.zakazchik AS ai_zakazchik
                    FROM zakupki z
                    INNER JOIN ai_results a ON a.reg_number = z.reg_number
                    WHERE z.processed_at IS NOT NULL
                    ORDER BY z.processed_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
                items = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        items.append(row_dict)
                return items, total

        result = self.execute_with_retry(_get)
        return result if result is not None else ([], 0)
