"""Repository for public user favorites."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from models.public_favorite import PublicFavorite

from .base import BaseRepository


class PublicFavoriteRepository(BaseRepository[PublicFavorite]):
    def create_table(self) -> bool:
        def _create():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                id_sql = "BIGSERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                ts_sql = "TIMESTAMP" if self.is_postgres else "TEXT"
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS public_favorites (
                        id {id_sql},
                        reg_number TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        created_at {ts_sql} NOT NULL,
                        FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number)
                    )
                    """
                )
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_public_favorites_user_reg ON public_favorites(user_email, reg_number)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_public_favorites_user_created ON public_favorites(user_email, created_at)"
                )
                conn.commit()
                return True

        return bool(self.execute_with_retry(_create))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_favorite(self, reg_number: str, user_email: str) -> bool:
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        if not reg or not email:
            return False

        def _add():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if self.is_postgres:
                    cursor.execute(
                        """
                        INSERT INTO public_favorites (reg_number, user_email, created_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT (user_email, reg_number) DO NOTHING
                        """,
                        (reg, email, self._now_iso()),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO public_favorites (reg_number, user_email, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (reg, email, self._now_iso()),
                    )
                conn.commit()
                return True

        return bool(self.execute_with_retry(_add))

    def remove_favorite(self, reg_number: str, user_email: str) -> bool:
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        if not reg or not email:
            return False

        def _remove():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM public_favorites WHERE reg_number = ? AND LOWER(user_email) = ?",
                    (reg, email),
                )
                conn.commit()
                return max(0, int(cursor.rowcount or 0)) > 0

        return bool(self.execute_with_retry(_remove))

    def is_favorite(self, reg_number: str, user_email: str) -> bool:
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        if not reg or not email:
            return False

        def _check():
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT 1 AS ok FROM public_favorites WHERE reg_number = ? AND LOWER(user_email) = ? LIMIT 1",
                    (reg, email),
                ).fetchone()
                return bool(row)

        return bool(self.execute_with_retry(_check))

    def get_favorite_reg_numbers_map(self, reg_numbers: List[str], user_email: str) -> dict[str, bool]:
        regs = [str(x).strip() for x in (reg_numbers or []) if str(x).strip()]
        email = (user_email or "").strip().lower()
        if not regs or not email:
            return {reg: False for reg in regs}

        def _get():
            with self.get_connection() as conn:
                placeholders = ",".join(["?"] * len(regs))
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT reg_number
                    FROM public_favorites
                    WHERE LOWER(user_email) = ? AND reg_number IN ({placeholders})
                    """,
                    [email] + regs,
                )
                rows = cursor.fetchall()
                present = set()
                for row in rows:
                    d = self.row_to_dict(row) or {}
                    reg = str(d.get("reg_number") or "").strip()
                    if reg:
                        present.add(reg)
                return {reg: reg in present for reg in regs}

        result = self.execute_with_retry(_get)
        return result or {reg: False for reg in regs}

    def get_favorites_page(self, user_email: str, offset: int = 0, limit: int = 20) -> tuple[List[dict], int]:
        email = (user_email or "").strip().lower()
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, min(200, int(limit or 20)))
        if not email:
            return [], 0

        def _get():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM public_favorites WHERE LOWER(user_email) = ?",
                    (email,),
                )
                total_row = cursor.fetchone()
                total_dict = self.row_to_dict(total_row)
                total = int((total_dict or {}).get("cnt") or 0)

                cursor.execute(
                    """
                    SELECT reg_number, user_email, created_at
                    FROM public_favorites
                    WHERE LOWER(user_email) = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (email, safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
                items = [self.row_to_dict(row) for row in rows if self.row_to_dict(row)]
                return items, total

        result = self.execute_with_retry(_get)
        if not result:
            return [], 0
        return result

    def save(self, entity: PublicFavorite) -> bool:
        return self.add_favorite(entity.reg_number, entity.user_email)

    def get_by_id(self, id: str) -> Optional[PublicFavorite]:
        def _get():
            with self.get_connection() as conn:
                row = conn.execute("SELECT * FROM public_favorites WHERE id = ?", (id,)).fetchone()
                row_dict = self.row_to_dict(row)
                return PublicFavorite.from_dict(row_dict) if row_dict else None

        return self.execute_with_retry(_get)

    def get_all(self) -> List[PublicFavorite]:
        def _all():
            with self.get_connection() as conn:
                rows = conn.execute("SELECT * FROM public_favorites ORDER BY id DESC").fetchall()
                out: List[PublicFavorite] = []
                for row in rows:
                    d = self.row_to_dict(row)
                    if d:
                        out.append(PublicFavorite.from_dict(d))
                return out

        return self.execute_with_retry(_all) or []

    def delete(self, id: str) -> bool:
        def _delete():
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM public_favorites WHERE id = ?", (id,))
                conn.commit()
                return max(0, int(cur.rowcount or 0)) > 0

        return bool(self.execute_with_retry(_delete))
