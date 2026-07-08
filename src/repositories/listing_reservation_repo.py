"""Repository for listing reservations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from models.listing_reservation import ListingReservation

from .base import BaseRepository


class ListingReservationRepository(BaseRepository[ListingReservation]):
    """CRUD and business operations for listing reservations."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                ts_sql = "TIMESTAMP" if self.is_postgres else "TEXT"
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS listing_reservations (
                        id {id_sql},
                        listing_id INTEGER NOT NULL,
                        reg_number TEXT NOT NULL,
                        reserved_by TEXT NOT NULL,
                        status TEXT NOT NULL,
                        reserved_at {ts_sql} NOT NULL,
                        expires_at {ts_sql} NOT NULL,
                        created_at {ts_sql} NOT NULL,
                        updated_at {ts_sql} NOT NULL,
                        FOREIGN KEY (listing_id) REFERENCES listings(id)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listing_res_listing_status ON listing_reservations(listing_id, status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listing_res_reg_status ON listing_reservations(reg_number, status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_listing_res_exp_status ON listing_reservations(expires_at, status)"
                )
                conn.commit()
                return True

        return self.execute_with_retry(_create) or False

    @staticmethod
    def _now_iso(now: Optional[datetime] = None) -> str:
        dt = now or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def expire_active_reservations(self, now: Optional[datetime] = None) -> int:
        now_iso = self._now_iso(now)

        def _expire():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE listing_reservations
                    SET status = ?, updated_at = ?
                    WHERE status = ? AND expires_at <= ?
                    """,
                    (self.EXPIRED, now_iso, self.ACTIVE, now_iso),
                )
                conn.commit()
                return max(0, int(cursor.rowcount or 0))

        return self.execute_with_retry(_expire) or 0

    def get_active_reserved_listing_ids(
        self,
        reg_number: Optional[str] = None,
        now: Optional[datetime] = None,
        expire: bool = True,
    ) -> set[int]:
        now_iso = self._now_iso(now)
        if expire:
            self.expire_active_reservations(now=now)

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if reg_number:
                    cursor.execute(
                        """
                        SELECT listing_id
                        FROM listing_reservations
                        WHERE status = ? AND expires_at > ? AND reg_number = ?
                        """,
                        (self.ACTIVE, now_iso, reg_number),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT listing_id
                        FROM listing_reservations
                        WHERE status = ? AND expires_at > ?
                        """,
                        (self.ACTIVE, now_iso),
                    )
                rows = cursor.fetchall()
                result: set[int] = set()
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict and row_dict.get("listing_id") is not None:
                        result.add(int(row_dict["listing_id"]))
                return result

        return self.execute_with_retry(_get) or set()

    def get_active_reserved_listing_ids_map(
        self,
        reg_numbers: List[str],
        now: Optional[datetime] = None,
        expire: bool = True,
    ) -> dict[str, set[int]]:
        safe_regs = [str(x).strip() for x in (reg_numbers or []) if str(x).strip()]
        if not safe_regs:
            return {}

        now_iso = self._now_iso(now)
        if expire:
            self.expire_active_reservations(now=now)

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(safe_regs))
                cursor.execute(
                    f"""
                    SELECT reg_number, listing_id
                    FROM listing_reservations
                    WHERE status = ? AND expires_at > ? AND reg_number IN ({placeholders})
                    """,
                    [self.ACTIVE, now_iso] + safe_regs,
                )
                rows = cursor.fetchall()
                result: dict[str, set[int]] = {reg: set() for reg in safe_regs}
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if not row_dict:
                        continue
                    reg = str(row_dict.get("reg_number") or "").strip()
                    listing_id = row_dict.get("listing_id")
                    if reg and listing_id is not None:
                        result.setdefault(reg, set()).add(int(listing_id))
                return result

        return self.execute_with_retry(_get) or {reg: set() for reg in safe_regs}

    def reserve_cheapest_available(
        self,
        reg_number: str,
        reserved_by: str,
        ttl_hours: int,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        reg = (reg_number or "").strip()
        if not reg:
            return None

        ttl = max(1, int(ttl_hours or 1))
        safe_reserved_by = (reserved_by or "anon").strip() or "anon"
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()
        expires_iso = (now_dt + timedelta(hours=ttl)).isoformat()

        def _reserve():
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if not self.is_postgres:
                    conn.execute("BEGIN IMMEDIATE")

                cursor.execute(
                    """
                    UPDATE listing_reservations
                    SET status = ?, updated_at = ?
                    WHERE status = ? AND expires_at <= ?
                    """,
                    (self.EXPIRED, now_iso, self.ACTIVE, now_iso),
                )

                if self.is_postgres:
                    cursor.execute(
                        """
                        SELECT l.id
                        FROM listings l
                        WHERE l.zakupka_reg_number = ?
                          AND NOT EXISTS (
                                SELECT 1
                                FROM listing_reservations r
                                WHERE r.listing_id = l.id
                                  AND r.status = ?
                                  AND r.expires_at > ?
                          )
                        ORDER BY l.price_rub ASC, COALESCE(l.rank, 2147483647) ASC, l.id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """,
                        (reg, self.ACTIVE, now_iso),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT l.id
                        FROM listings l
                        LEFT JOIN listing_reservations r
                          ON r.listing_id = l.id
                         AND r.status = ?
                         AND r.expires_at > ?
                        WHERE l.zakupka_reg_number = ?
                          AND r.id IS NULL
                        ORDER BY l.price_rub ASC, COALESCE(l.rank, 2147483647) ASC, l.id ASC
                        LIMIT 1
                        """,
                        (self.ACTIVE, now_iso, reg),
                    )

                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                if not row_dict or row_dict.get("id") is None:
                    conn.commit()
                    return None

                listing_id = int(row_dict["id"])
                cursor.execute(
                    """
                    INSERT INTO listing_reservations (
                        listing_id,
                        reg_number,
                        reserved_by,
                        status,
                        reserved_at,
                        expires_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        listing_id,
                        reg,
                        safe_reserved_by,
                        self.ACTIVE,
                        now_iso,
                        expires_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                reservation_id = cursor.lastrowid
                conn.commit()
                return {
                    "reservation_id": reservation_id,
                    "listing_id": listing_id,
                    "reg_number": reg,
                    "expires_at": expires_iso,
                    "status": self.ACTIVE,
                }

        return self.execute_with_retry(_reserve)

    def save(self, entity: ListingReservation) -> bool:
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = self.build_upsert_sql(
                    table="listing_reservations",
                    insert_columns=[
                        "id",
                        "listing_id",
                        "reg_number",
                        "reserved_by",
                        "status",
                        "reserved_at",
                        "expires_at",
                        "created_at",
                        "updated_at",
                    ],
                    conflict_columns=["id"],
                )
                cursor.execute(
                    sql,
                    (
                        entity.id,
                        entity.listing_id,
                        entity.reg_number,
                        entity.reserved_by,
                        entity.status,
                        entity.reserved_at,
                        entity.expires_at,
                        entity.created_at,
                        entity.updated_at,
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_save) or False

    def get_by_id(self, id: str) -> Optional[ListingReservation]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listing_reservations WHERE id = ?", (id,))
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                return ListingReservation.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_all(self) -> List[ListingReservation]:
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM listing_reservations ORDER BY id DESC")
                rows = cursor.fetchall()
                result: List[ListingReservation] = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(ListingReservation.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_all) or []

    def delete(self, id: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM listing_reservations WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False
