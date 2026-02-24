"""Base repository with SQLite/PostgreSQL support."""

from __future__ import annotations

import sqlite3
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generic, List, Optional, TypeVar

from utils.logger import get_logger

try:
    import psycopg2
    from psycopg2 import extras as psycopg2_extras
except Exception:  # pragma: no cover - optional dependency
    psycopg2 = None
    psycopg2_extras = None

T = TypeVar("T")


class _CursorAdapter:
    """Normalizes cursor API and placeholder style across DB engines."""

    def __init__(self, cursor: Any, sql_mapper):
        self._cursor = cursor
        self._sql_mapper = sql_mapper

    def execute(self, sql: str, params: Optional[tuple | list] = None):
        if params is None:
            params = ()
        self._cursor.execute(self._sql_mapper(sql), params)
        return self

    def executemany(self, sql: str, params_seq):
        self._cursor.executemany(self._sql_mapper(sql), params_seq)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


class _ConnectionAdapter:
    """Adds connection.execute for psycopg2 and maps placeholders."""

    def __init__(self, conn: Any, sql_mapper):
        self._conn = conn
        self._sql_mapper = sql_mapper

    def cursor(self):
        return _CursorAdapter(self._conn.cursor(), self._sql_mapper)

    def execute(self, sql: str, params: Optional[tuple | list] = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, item):
        return getattr(self._conn, item)


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository for shared DB logic."""

    def __init__(
        self,
        db_path: Optional[str],
        database_url: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.db_path = db_path
        self.database_url = database_url
        self.max_retries = max_retries
        self.logger = get_logger(self.__class__.__name__)
        self.is_postgres = bool(database_url)
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensures local directory exists for SQLite mode."""
        if self.is_postgres:
            return
        if not self.db_path:
            raise ValueError("DATABASE_PATH is required when DATABASE_URL is not set")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _sql(self, sql: str) -> str:
        """Converts DB-API placeholders for PostgreSQL."""
        if not self.is_postgres:
            return sql
        # Project SQL uses positional "?" placeholders.
        return sql.replace("?", "%s")

    @contextmanager
    def get_connection(self):
        """Context manager returning DB-agnostic connection adapter."""
        raw_conn = None
        try:
            if self.is_postgres:
                if psycopg2 is None:
                    raise RuntimeError(
                        "DATABASE_URL is set but psycopg2 is not installed. "
                        "Install dependency: psycopg2-binary"
                    )
                raw_conn = psycopg2.connect(
                    self.database_url,
                    connect_timeout=30,
                    cursor_factory=psycopg2_extras.DictCursor,
                )
            else:
                raw_conn = sqlite3.connect(self.db_path, timeout=30.0)
                raw_conn.row_factory = sqlite3.Row
                raw_conn.execute("PRAGMA busy_timeout = 30000")
                raw_conn.execute("PRAGMA journal_mode = WAL")

            yield _ConnectionAdapter(raw_conn, self._sql)
        finally:
            if raw_conn is not None:
                raw_conn.close()

    def _is_retryable_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        if isinstance(exc, sqlite3.OperationalError):
            return "database is locked" in msg or "database is busy" in msg
        if psycopg2 is not None and isinstance(exc, psycopg2.OperationalError):
            return True
        retryable_pg_markers = (
            "deadlock detected",
            "could not serialize access",
            "connection exception",
            "connection refused",
            "connection reset",
        )
        return any(marker in msg for marker in retryable_pg_markers)

    def execute_with_retry(self, operation, *args, **kwargs):
        """Executes operation with retries for transient DB errors."""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                return operation(*args, **kwargs)
            except Exception as exc:
                if not self._is_retryable_error(exc):
                    raise
                retry_count += 1
                self.logger.warning(
                    "Transient DB error, retry %s/%s: %s",
                    retry_count,
                    self.max_retries,
                    exc,
                )
                time.sleep(1)
        self.logger.error("Operation failed after %s retries", self.max_retries)
        return None

    def row_to_dict(self, row: Any) -> Optional[dict]:
        """Converts sqlite Row / psycopg2 DictRow / dict to plain dict."""
        if row is None:
            return None
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        try:
            return dict(row)
        except Exception:
            return None

    def build_upsert_sql(
        self,
        table: str,
        insert_columns: List[str],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> str:
        """Builds portable upsert SQL (SQLite >=3.24 and PostgreSQL)."""
        if update_columns is None:
            update_columns = [c for c in insert_columns if c not in conflict_columns]

        cols_sql = ", ".join(insert_columns)
        placeholders = ", ".join(["?"] * len(insert_columns))
        conflict_sql = ", ".join(conflict_columns)

        if update_columns:
            update_sql = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            return (
                f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
            )
        return (
            f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_sql}) DO NOTHING"
        )

    @abstractmethod
    def create_table(self) -> bool:
        """Creates table if needed."""
        pass

    @abstractmethod
    def save(self, entity: T) -> bool:
        """Saves entity."""
        pass

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]:
        """Returns entity by id."""
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """Returns all entities."""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Deletes entity."""
        pass
