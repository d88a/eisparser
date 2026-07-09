"""Repository for collected listings."""

from datetime import datetime
from typing import List, Optional

from models.listing import Listing

from .base import BaseRepository


class ListingRepository(BaseRepository[Listing]):
    """CRUD operations for listings."""

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS listings (
                        id {id_sql},
                        zakupka_reg_number TEXT NOT NULL,
                        rank INTEGER,
                        price_rub INTEGER NOT NULL,
                        address TEXT,
                        rooms INTEGER,
                        area_m2 REAL,
                        floor INTEGER,
                        building_floors INTEGER,
                        building_year INTEGER,
                        two_gis_url TEXT,
                        external_source TEXT,
                        external_url TEXT,
                        fetched_at TEXT NOT NULL,
                        query_url TEXT,
                        FOREIGN KEY (zakupka_reg_number) REFERENCES zakupki(reg_number)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listings_zakupka ON listings(zakupka_reg_number)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_rub)"
                )
                conn.commit()
                return True

        return self.execute_with_retry(_create) or False

    def save(self, listing: Listing) -> bool:
        raise NotImplementedError("Use save_batch for listings")

    def save_batch(self, reg_number: str, listings: List[Listing], query_url: str = None) -> int:
        deleted = self.delete_for_zakupka(reg_number)
        if deleted > 0:
            self.logger.info("Deleted %s old listings for %s", deleted, reg_number)

        if not listings:
            return 0

        def _save_batch():
            fetched_at = datetime.now().isoformat()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                inserted = 0

                for listing in listings:
                    data = listing.to_dict() if hasattr(listing, "to_dict") else listing
                    cursor.execute(
                        """
                        INSERT INTO listings (
                            zakupka_reg_number, rank, price_rub, address,
                            rooms, area_m2, floor, building_floors, building_year,
                            two_gis_url, external_source, external_url,
                            fetched_at, query_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reg_number,
                            data.get("rank"),
                            data.get("price_rub"),
                            data.get("address"),
                            data.get("rooms"),
                            data.get("area_m2"),
                            data.get("floor"),
                            data.get("building_floors"),
                            data.get("building_year"),
                            data.get("two_gis_url"),
                            data.get("external_source"),
                            data.get("external_url"),
                            fetched_at,
                            query_url,
                        ),
                    )
                    inserted += 1

                conn.commit()
                return inserted

        return self.execute_with_retry(_save_batch) or 0

    def get_by_id(self, id: str) -> Optional[Listing]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listings WHERE id = ?", (id,))
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                return Listing.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_all(self) -> List[Listing]:
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listings ORDER BY price_rub")
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Listing.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_all) or []

    def get_for_zakupka(self, reg_number: str) -> List[Listing]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM listings WHERE zakupka_reg_number = ? ORDER BY rank",
                    (reg_number,),
                )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(Listing.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get) or []

    def get_stats_for_zakupki(self, reg_numbers: List[str]) -> dict[str, dict]:
        regs = [str(x).strip() for x in (reg_numbers or []) if str(x).strip()]
        if not regs:
            return {}

        def _get_stats_batch(batch_regs):
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(batch_regs))
                cursor.execute(
                    f"""
                    SELECT
                        zakupka_reg_number AS reg_number,
                        COUNT(*) AS listings_count,
                        MIN(price_rub) AS min_price_rub
                    FROM listings
                    WHERE zakupka_reg_number IN ({placeholders})
                    GROUP BY zakupka_reg_number
                    """,
                    batch_regs,
                )
                rows = cursor.fetchall()
                batch_result = {}
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if not row_dict:
                        continue
                    reg = str(row_dict.get("reg_number") or "").strip()
                    if not reg:
                        continue
                    batch_result[reg] = {
                        "listings_count": int(row_dict.get("listings_count") or 0),
                        "min_price_rub": row_dict.get("min_price_rub"),
                    }
                return batch_result

        # Process in batches to avoid query timeouts with large IN clauses
        batch_size = 500
        result = {reg: {"listings_count": 0, "min_price_rub": None} for reg in regs}
        for i in range(0, len(regs), batch_size):
            batch = regs[i : i + batch_size]
            batch_stats = self.execute_with_retry(_get_stats_batch, batch)
            if batch_stats:
                result.update(batch_stats)
        return result

    def delete(self, id: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM listings WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False

    def delete_for_zakupka(self, reg_number: str) -> int:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM listings WHERE zakupka_reg_number = ?", (reg_number,))
                conn.commit()
                return cursor.rowcount

        return self.execute_with_retry(_delete) or 0

    def count(self) -> int:
        def _count():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM listings")
                row = cursor.fetchone()
                return row[0] if row else 0

        return self.execute_with_retry(_count) or 0
