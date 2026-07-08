"""Repository for procurement-level reservations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from models.zakupka_reservation import ZakupkaReservation

from .base import BaseRepository


class ZakupkaReservationRepository(BaseRepository[ZakupkaReservation]):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REASON_MANUAL = "manual_unreserve"
    REASON_EXPIRED = "expired"
    REASON_OTHER = "other"

    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                ts_sql = "TIMESTAMP" if self.is_postgres else "TEXT"
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS zakupka_reservations (
                        id {id_sql},
                        reg_number TEXT NOT NULL,
                        reserved_by TEXT NOT NULL,
                        status TEXT NOT NULL,
                        reserved_at {ts_sql} NOT NULL,
                        expires_at {ts_sql} NOT NULL,
                        end_reason TEXT,
                        created_at {ts_sql} NOT NULL,
                        updated_at {ts_sql} NOT NULL,
                        FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_zakupka_res_reg_status ON zakupka_reservations(reg_number, status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_zakupka_res_exp_status ON zakupka_reservations(expires_at, status)"
                )
                try:
                    cursor.execute("ALTER TABLE zakupka_reservations ADD COLUMN end_reason TEXT")
                except Exception:
                    pass
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
                    UPDATE zakupka_reservations
                    SET status = ?, end_reason = ?, updated_at = ?
                    WHERE status = ? AND expires_at <= ?
                    """,
                    (self.EXPIRED, self.REASON_EXPIRED, now_iso, self.ACTIVE, now_iso),
                )
                conn.commit()
                return max(0, int(cursor.rowcount or 0))

        return self.execute_with_retry(_expire) or 0

    def get_active_reservations_map(
        self,
        reg_numbers: List[str],
        now: Optional[datetime] = None,
        expire: bool = True,
    ) -> dict[str, str]:
        regs = [str(x).strip() for x in (reg_numbers or []) if str(x).strip()]
        if not regs:
            return {}

        now_iso = self._now_iso(now)
        if expire:
            self.expire_active_reservations(now=now)

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(regs))
                cursor.execute(
                    f"""
                    SELECT reg_number, expires_at
                    FROM zakupka_reservations
                    WHERE status = ? AND expires_at > ? AND reg_number IN ({placeholders})
                    ORDER BY expires_at DESC
                    """,
                    [self.ACTIVE, now_iso] + regs,
                )
                rows = cursor.fetchall()
                result: dict[str, str] = {}
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if not row_dict:
                        continue
                    reg = str(row_dict.get("reg_number") or "").strip()
                    exp = row_dict.get("expires_at")
                    if reg and exp and reg not in result:
                        result[reg] = str(exp)
                return result

        return self.execute_with_retry(_get) or {}

    def reserve_procurement(
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
                    UPDATE zakupka_reservations
                    SET status = ?, end_reason = ?, updated_at = ?
                    WHERE status = ? AND expires_at <= ?
                    """,
                    (self.EXPIRED, self.REASON_EXPIRED, now_iso, self.ACTIVE, now_iso),
                )

                if self.is_postgres:
                    cursor.execute("SELECT reg_number FROM zakupki WHERE reg_number = ? FOR UPDATE", (reg,))
                else:
                    cursor.execute("SELECT reg_number FROM zakupki WHERE reg_number = ?", (reg,))
                if not cursor.fetchone():
                    conn.commit()
                    return None

                cursor.execute(
                    """
                    SELECT id, expires_at, reserved_by
                    FROM zakupka_reservations
                    WHERE reg_number = ? AND status = ? AND expires_at > ?
                    ORDER BY expires_at DESC
                    LIMIT 1
                    """,
                    (reg, self.ACTIVE, now_iso),
                )
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                if row_dict:
                    owner = str(row_dict.get("reserved_by") or "").strip().lower()
                    conn.commit()
                    if owner and owner != safe_reserved_by.lower():
                        return {
                            "reg_number": reg,
                            "expires_at": str(row_dict.get("expires_at")),
                            "status": self.ACTIVE,
                            "already_reserved": False,
                            "reserved_by_other": True,
                        }
                    return {
                        "reg_number": reg,
                        "expires_at": str(row_dict.get("expires_at")),
                        "status": self.ACTIVE,
                        "already_reserved": True,
                    }

                cursor.execute(
                    """
                    INSERT INTO zakupka_reservations (
                        reg_number,
                        reserved_by,
                        status,
                        reserved_at,
                        expires_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reg,
                        safe_reserved_by,
                        self.ACTIVE,
                        now_iso,
                        expires_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()
                return {
                    "reg_number": reg,
                    "expires_at": expires_iso,
                    "status": self.ACTIVE,
                    "already_reserved": False,
                }

        return self.execute_with_retry(_reserve)

    def get_active_by_reg(self, reg_number: str, now: Optional[datetime] = None) -> Optional[dict]:
        reg = (reg_number or "").strip()
        if not reg:
            return None
        now_iso = self._now_iso(now)
        self.expire_active_reservations(now=now)

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT reg_number, reserved_by, reserved_at, expires_at, status, end_reason, updated_at
                    FROM zakupka_reservations
                    WHERE reg_number = ? AND status = ? AND expires_at > ?
                    ORDER BY expires_at DESC
                    LIMIT 1
                    """,
                    (reg, self.ACTIVE, now_iso),
                )
                row = cursor.fetchone()
                return self.row_to_dict(row)

        return self.execute_with_retry(_get)

    def get_active_page(
        self,
        offset: int = 0,
        limit: int = 20,
        reserved_by: Optional[str] = None,
        now: Optional[datetime] = None,
        expire: bool = True,
    ) -> tuple[List[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, min(200, int(limit or 20)))
        now_iso = self._now_iso(now)
        reserved_by_norm = (reserved_by or "").strip().lower()
        if expire:
            self.expire_active_reservations(now=now)

        def _get_page():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if reserved_by_norm:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM zakupka_reservations
                        WHERE status = ? AND expires_at > ? AND LOWER(reserved_by) = ?
                        """,
                        (self.ACTIVE, now_iso, reserved_by_norm),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM zakupka_reservations
                        WHERE status = ? AND expires_at > ?
                        """,
                        (self.ACTIVE, now_iso),
                    )
                total_row = cursor.fetchone()
                total_dict = self.row_to_dict(total_row)
                total = int((total_dict or {}).get("cnt") or 0)

                if reserved_by_norm:
                    cursor.execute(
                        """
                        SELECT reg_number, reserved_by, reserved_at, expires_at, status
                        FROM zakupka_reservations
                        WHERE status = ? AND expires_at > ? AND LOWER(reserved_by) = ?
                        ORDER BY expires_at ASC
                        LIMIT ? OFFSET ?
                        """,
                        (self.ACTIVE, now_iso, reserved_by_norm, safe_limit, safe_offset),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT reg_number, reserved_by, reserved_at, expires_at, status
                        FROM zakupka_reservations
                        WHERE status = ? AND expires_at > ?
                        ORDER BY expires_at ASC
                        LIMIT ? OFFSET ?
                        """,
                        (self.ACTIVE, now_iso, safe_limit, safe_offset),
                    )
                rows = cursor.fetchall()
                items: List[dict] = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        items.append(row_dict)
                return items, total

        result = self.execute_with_retry(_get_page)
        if not result:
            return [], 0
        return result

    def cancel_active(
        self,
        reg_number: str,
        reserved_by: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        reg = (reg_number or "").strip()
        if not reg:
            return False

        now_iso = self._now_iso(now)
        reserved_by_norm = (reserved_by or "").strip().lower()

        def _cancel():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if reserved_by_norm:
                    cursor.execute(
                        """
                        UPDATE zakupka_reservations
                        SET status = ?, end_reason = ?, updated_at = ?
                        WHERE reg_number = ? AND status = ? AND expires_at > ? AND LOWER(reserved_by) = ?
                        """,
                        (self.CANCELLED, self.REASON_MANUAL, now_iso, reg, self.ACTIVE, now_iso, reserved_by_norm),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE zakupka_reservations
                        SET status = ?, end_reason = ?, updated_at = ?
                        WHERE reg_number = ? AND status = ? AND expires_at > ?
                        """,
                        (self.CANCELLED, self.REASON_MANUAL, now_iso, reg, self.ACTIVE, now_iso),
                    )
                conn.commit()
                return max(0, int(cursor.rowcount or 0)) > 0

        return bool(self.execute_with_retry(_cancel))

    def get_history_page(
        self,
        user_email: str,
        offset: int = 0,
        limit: int = 20,
        now: Optional[datetime] = None,
        expire: bool = True,
    ) -> tuple[List[dict], int]:
        email = (user_email or "").strip().lower()
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, min(200, int(limit or 20)))
        now_iso = self._now_iso(now)
        if not email:
            return [], 0
        if expire:
            self.expire_active_reservations(now=now)

        def _get_page():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM zakupka_reservations
                    WHERE LOWER(reserved_by) = ? AND (status <> ? OR expires_at <= ?)
                    """,
                    (email, self.ACTIVE, now_iso),
                )
                total_row = cursor.fetchone()
                total_dict = self.row_to_dict(total_row)
                total = int((total_dict or {}).get("cnt") or 0)

                cursor.execute(
                    """
                    SELECT reg_number, reserved_by, reserved_at, expires_at, status, end_reason, updated_at
                    FROM zakupka_reservations
                    WHERE LOWER(reserved_by) = ? AND (status <> ? OR expires_at <= ?)
                    ORDER BY updated_at DESC, expires_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (email, self.ACTIVE, now_iso, safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
                items: List[dict] = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        if not row_dict.get("end_reason"):
                            status = str(row_dict.get("status") or "").strip().lower()
                            if status == self.CANCELLED:
                                row_dict["end_reason"] = self.REASON_MANUAL
                            elif status == self.EXPIRED:
                                row_dict["end_reason"] = self.REASON_EXPIRED
                            else:
                                row_dict["end_reason"] = self.REASON_OTHER
                        items.append(row_dict)
                return items, total

        result = self.execute_with_retry(_get_page)
        if not result:
            return [], 0
        return result

    def save(self, entity: ZakupkaReservation) -> bool:
        def _save():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = self.build_upsert_sql(
                    table="zakupka_reservations",
                    insert_columns=[
                        "id",
                        "reg_number",
                        "reserved_by",
                        "status",
                        "reserved_at",
                        "expires_at",
                        "end_reason",
                        "created_at",
                        "updated_at",
                    ],
                    conflict_columns=["id"],
                )
                cursor.execute(
                    sql,
                    (
                        entity.id,
                        entity.reg_number,
                        entity.reserved_by,
                        entity.status,
                        entity.reserved_at,
                        entity.expires_at,
                        entity.end_reason,
                        entity.created_at,
                        entity.updated_at,
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_save) or False

    def get_by_id(self, id: str) -> Optional[ZakupkaReservation]:
        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupka_reservations WHERE id = ?", (id,))
                row = cursor.fetchone()
                row_dict = self.row_to_dict(row)
                return ZakupkaReservation.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_all(self) -> List[ZakupkaReservation]:
        def _get_all():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM zakupka_reservations ORDER BY id DESC")
                rows = cursor.fetchall()
                result: List[ZakupkaReservation] = []
                for row in rows:
                    row_dict = self.row_to_dict(row)
                    if row_dict:
                        result.append(ZakupkaReservation.from_dict(row_dict))
                return result

        return self.execute_with_retry(_get_all) or []

    def delete(self, id: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM zakupka_reservations WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0

        return self.execute_with_retry(_delete) or False
