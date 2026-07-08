"""Health-check aggregation for API, DB and background workers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from services.worker_service import WorkerService, psycopg2


@dataclass
class WorkerProbe:
    status: str
    had_error: bool = False


class HealthService:
    """Builds stable health payload that never raises to API layer."""

    def __init__(self, pipeline: Any):
        self.pipeline = pipeline

    def get_health_payload(self) -> dict:
        db_status = "ok"
        try:
            self._probe_db()
        except Exception:
            db_status = "error"

        ingest_probe = self._probe_worker_lock(WorkerService.DEFAULT_LOCK_KEY_INGEST)
        listing_probe = self._probe_worker_lock(WorkerService.DEFAULT_LOCK_KEY_LISTING)

        degraded = db_status == "error" or ingest_probe.had_error or listing_probe.had_error
        return {
            "status": "degraded" if degraded else "ok",
            "api": "ok",
            "db": db_status,
            "workers": {
                "ingest": ingest_probe.status,
                "listing": listing_probe.status,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _probe_db(self) -> None:
        with self.pipeline.db.zakupki.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()

    def _probe_worker_lock(self, lock_key: int) -> WorkerProbe:
        db_url = str(getattr(self.pipeline.db, "database_url", "") or "").strip()
        if not db_url:
            return WorkerProbe(status="unknown", had_error=False)
        if psycopg2 is None:
            return WorkerProbe(status="unknown", had_error=False)

        conn = None
        try:
            conn = psycopg2.connect(db_url, connect_timeout=5)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (int(lock_key),))
                acquired = bool(cur.fetchone()[0])
                if acquired:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (int(lock_key),))
                    return WorkerProbe(status="inactive", had_error=False)
                return WorkerProbe(status="active", had_error=False)
        except Exception:
            return WorkerProbe(status="unknown", had_error=True)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
