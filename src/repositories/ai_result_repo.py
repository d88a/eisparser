"""Repository for AI analysis results."""

from typing import List, Optional

from models.ai_result import AIResult

from .base import BaseRepository


class AIResultRepository(BaseRepository[AIResult]):
    """CRUD for AI results."""

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_results (
                        reg_number TEXT PRIMARY KEY,
                        zakupka_name TEXT,
                        address TEXT,
                        city TEXT,
                        area_min_m2 REAL,
                        area_max_m2 REAL,
                        rooms TEXT,
                        rooms_parsed TEXT,
                        floor TEXT,
                        building_floors_min TEXT,
                        year_build_str TEXT,
                        wear_percent REAL,
                        zakazchik TEXT,
                        FOREIGN KEY (reg_number) REFERENCES zakupki (reg_number)
                    )
                    """
                )
                conn.commit()
                return True

        return self.execute_with_retry(_create) or False

    def save(self, result: AIResult) -> bool:
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = self.build_upsert_sql(
                    table="ai_results",
                    insert_columns=[
                        "reg_number",
                        "zakupka_name",
                        "address",
                        "city",
                        "area_min_m2",
                        "area_max_m2",
                        "rooms",
                        "rooms_parsed",
                        "floor",
                        "building_floors_min",
                        "year_build_str",
                        "wear_percent",
                        "zakazchik",
                    ],
                    conflict_columns=["reg_number"],
                )
                cursor.execute(
                    sql,
                    (
                        result.reg_number,
                        result.zakupka_name,
                        result.address,
                        result.city,
                        result.area_min_m2,
                        result.area_max_m2,
                        result.rooms,
                        result.rooms_parsed,
                        result.floor,
                        result.building_floors_min,
                        result.year_build_str,
                        result.wear_percent,
                        result.zakazchik,
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_save) or False

    def get_by_id(self, reg_number: str) -> Optional[AIResult]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ai_results WHERE reg_number = ?", (reg_number,))
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                return AIResult.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_by_reg_numbers_map(self, reg_numbers: List[str]) -> dict[str, AIResult]:
        regs = [str(x).strip() for x in (reg_numbers or []) if str(x).strip()]
        if not regs:
            return {}

        def _get_map():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(regs))
                cursor.execute(
                    f"SELECT * FROM ai_results WHERE reg_number IN ({placeholders})",
                    regs,
                )
                rows = cursor.fetchall()
                result: dict[str, AIResult] = {}
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if not row_dict:
                        continue
                    entity = AIResult.from_dict(row_dict)
                    result[entity.reg_number] = entity
                return result

        return self.execute_with_retry(_get_map) or {}

    def get_all(self) -> List[AIResult]:
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ai_results ORDER BY reg_number DESC")
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(AIResult.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_all) or []

    def delete(self, reg_number: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ai_results WHERE reg_number = ?", (reg_number,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False

    def update_rooms_parsed(self, reg_number: str, rooms_parsed: str) -> bool:
        def _update():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE ai_results SET rooms_parsed = ? WHERE reg_number = ?",
                    (rooms_parsed, reg_number),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_update) or False

    def get_stage3_page(self, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) AS c FROM ai_results")
                count_row = cursor.fetchone()
                total = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])

                cursor.execute(
                    """
                    SELECT
                        a.reg_number,
                        a.city AS ai_city,
                        a.area_min_m2 AS ai_area_min,
                        a.area_max_m2 AS ai_area_max,
                        z.description,
                        z.update_date,
                        z.bid_end_date,
                        z.initial_price,
                        z.link,
                        z.two_gis_url,
                        z.processed_at
                    FROM ai_results a
                    LEFT JOIN zakupki z ON z.reg_number = a.reg_number
                    ORDER BY
                        CASE WHEN z.processed_at IS NULL THEN 1 ELSE 0 END,
                        z.processed_at DESC,
                        z.update_date DESC
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
