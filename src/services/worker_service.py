"""Background worker for automatic Stage execution."""

from __future__ import annotations

import os
import signal
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from config.settings import settings
from models.statuses import STAGE4_QUEUE_STATUSES, ZakupkaStatus
from utils.logger import get_logger

try:
    import psycopg
except Exception:  # pragma: no cover - optional runtime dependency
    psycopg = None

if TYPE_CHECKING:  # pragma: no cover
    from pipeline import Pipeline


class WorkerService:
    """Runs stages in a periodic loop."""

    MODE_ALL = "all"
    MODE_INGEST = "ingest"
    MODE_LISTING = "listing"

    DEFAULT_LOCK_KEY_ALL = 704127301905221
    DEFAULT_LOCK_KEY_INGEST = 704127301905222
    DEFAULT_LOCK_KEY_LISTING = 704127301905223
    LOCK_BUSY_EXIT_CODE = 75

    def __init__(
        self,
        pipeline: "Pipeline",
        interval: int = 300,
        limit: int = 10,
        top_n: int = 10,
        get_details: bool = False,
        mode: str = MODE_ALL,
        lock_key: Optional[int] = None,
    ):
        mode_value = (mode or self.MODE_ALL).strip().lower()
        if mode_value not in (self.MODE_ALL, self.MODE_INGEST, self.MODE_LISTING):
            raise ValueError(f"Unsupported worker mode: {mode}")

        self.pipeline = pipeline
        self.interval = max(1, int(interval))
        self.limit = max(1, int(limit))
        self.top_n = max(1, int(top_n))
        self.get_details = bool(get_details)
        self.mode = mode_value
        if lock_key is None:
            if self.mode == self.MODE_INGEST:
                self.lock_key = self.DEFAULT_LOCK_KEY_INGEST
            elif self.mode == self.MODE_LISTING:
                self.lock_key = self.DEFAULT_LOCK_KEY_LISTING
            else:
                self.lock_key = self.DEFAULT_LOCK_KEY_ALL
        else:
            self.lock_key = int(lock_key)
        self.enable_stage4 = bool(settings.worker_enable_stage4)

        self.logger = get_logger("worker")
        self._stop_event = threading.Event()
        self._lock_conn = None
        self._lock_busy = False

    def request_stop(self, signum: Optional[int] = None, _frame=None):
        if signum is not None:
            self.logger.info("Stop signal received: %s", signum)
        self._stop_event.set()

    def _install_signal_handlers(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.request_stop)
            except Exception:
                # Some runtimes/threads do not allow signal handlers.
                pass

    def _acquire_advisory_lock(self) -> bool:
        self._lock_busy = False
        db_url = self.pipeline.db.database_url
        if not db_url:
            self.logger.warning(
                "DATABASE_URL is not set; running without PostgreSQL advisory lock in fallback mode"
            )
            return True

        if psycopg is None:
            self.logger.error("psycopg is required for PostgreSQL advisory lock")
            return False

        try:
            conn = psycopg.connect(db_url, connect_timeout=10)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (self.lock_key,))
                acquired = bool(cur.fetchone()[0])
            if not acquired:
                self._lock_busy = True
                conn.close()
                self.logger.warning(
                    "Worker is already running (advisory lock %s is busy). Exiting.",
                    self.lock_key,
                )
                return False

            self._lock_conn = conn
            self.logger.info("Advisory lock acquired: %s", self.lock_key)
            return True
        except Exception:
            self.logger.exception("Failed to acquire advisory lock")
            return False

    def _release_advisory_lock(self):
        if not self._lock_conn:
            return
        try:
            with self._lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (self.lock_key,))
            self.logger.info("Advisory lock released: %s", self.lock_key)
        except Exception:
            self.logger.exception("Failed to release advisory lock")
        finally:
            try:
                self._lock_conn.close()
            except Exception:
                pass
            self._lock_conn = None

    def _run_stage(self, stage_name: str, fn):
        self.logger.info("%s started", stage_name)
        try:
            result = fn()
            if result is None:
                self.logger.info("%s finished", stage_name)
                return None

            self.logger.info(
                "%s finished: success=%s message=%s",
                stage_name,
                getattr(result, "success", None),
                getattr(result, "message", ""),
            )
            errors = getattr(result, "errors", None) or []
            if errors:
                self.logger.error("%s errors: %s", stage_name, errors)
            return result
        except Exception:
            self.logger.exception("%s failed with unexpected error", stage_name)
            return None

    def _reg_numbers_by_statuses(self, statuses: list[str], limit: int) -> list[str]:
        items = self.pipeline.db.zakupki.get_by_statuses_limited_ordered(statuses, limit)
        return [z.reg_number for z in items]

    def _reg_numbers_by_status(self, status: str, limit: int) -> list[str]:
        return self._reg_numbers_by_statuses([status], limit)

    def _run_stage4_batch(self, reg_numbers: list[str]):
        self.logger.info("Stage 4 started for %s purchases", len(reg_numbers))

        processed = 0
        total_listings = 0
        errors = []

        for reg_number in reg_numbers:
            try:
                zakupka = self.pipeline.eis.get_zakupka(reg_number)
                if not zakupka or not zakupka.two_gis_url:
                    reason = "no_two_gis_url"
                    errors.append(f"{reg_number}: {reason}")
                    self.logger.info(
                        "stage_progress reg_number=%s stage=4 result=skip reason=%s",
                        reg_number,
                        reason,
                    )
                    continue

                result = self.pipeline.run_stage4_for_zakupka(
                    reg_number=reg_number,
                    url=zakupka.two_gis_url,
                    top_n=self.top_n,
                    get_details=self.get_details,
                )
                processed += 1
                total_listings += result.actual_n
                if result.error:
                    errors.append(f"{reg_number}: {result.error}")
                    self.logger.info(
                        "stage_progress reg_number=%s stage=4 result=error reason=%s",
                        reg_number,
                        result.error,
                    )
                else:
                    self.logger.info(
                        "stage_progress reg_number=%s stage=4 result=ok reason=listings=%s",
                        reg_number,
                        result.actual_n,
                    )
            except Exception as exc:
                self.logger.exception("Stage 4 failed for %s", reg_number)
                errors.append(f"{reg_number}: {exc}")
                try:
                    self.pipeline.db.zakupki.update_status(reg_number, ZakupkaStatus.STAGE4_ERROR)
                except Exception:
                    self.logger.exception("Failed to mark %s for %s", ZakupkaStatus.STAGE4_ERROR, reg_number)
                self.logger.info(
                    "stage_progress reg_number=%s stage=4 result=error reason=%s",
                    reg_number,
                    exc,
                )

        self.logger.info(
            "Stage 4 finished: processed=%s total_listings=%s errors=%s",
            processed,
            total_listings,
            len(errors),
        )
        if errors:
            self.logger.error("Stage 4 errors: %s", errors)

    def run_cycle_all(self, cycle_number: int):
        cycle_started = time.time()
        self.logger.info("Cycle %s started", cycle_number)

        stage1_result = self._run_stage("Stage 1", lambda: self.pipeline.run_stage1(limit=self.limit))
        if stage1_result is not None and not bool(getattr(stage1_result, "success", True)):
            self.logger.warning(
                "Stage 1 degraded in cycle %s: reason=%s",
                cycle_number,
                getattr(stage1_result, "message", "unknown"),
            )
        stage1_saved = (getattr(stage1_result, "data", {}) or {}).get("saved_new")
        if stage1_saved is not None:
            self.logger.info("Cycle %s new purchases from Stage 1: %s", cycle_number, stage1_saved)

        stage2_probe, stage2_total = self.pipeline.get_stage2_pending_page(offset=0, limit=1)
        if stage2_probe:
            self.logger.info("Stage 2 pending probe: total=%s", stage2_total)
            self._run_stage(
                "Stage 2",
                lambda: self.pipeline.run_stage2(limit=self.limit, overwrite=False),
            )
        else:
            self.logger.info("Stage 2 skipped: no purchases pending Stage 2")

        stage3_reg_numbers = self._reg_numbers_by_status(ZakupkaStatus.AI_READY, self.limit)
        if stage3_reg_numbers:
            self._run_stage(
                "Stage 3",
                lambda: self.pipeline.run_stage3(reg_numbers=stage3_reg_numbers, overwrite=False),
            )
        else:
            self.logger.info("Stage 3 skipped: no purchases with status %s", ZakupkaStatus.AI_READY)

        if not self.enable_stage4:
            self.logger.info("Stage 4 disabled by config (WORKER_ENABLE_STAGE4=false)")
        else:
            stage4_reg_numbers = self._reg_numbers_by_statuses(list(STAGE4_QUEUE_STATUSES), self.limit)
            if stage4_reg_numbers:
                self._run_stage4_batch(stage4_reg_numbers)
            else:
                self.logger.info("Stage 4 skipped: no purchases with statuses %s", ",".join(STAGE4_QUEUE_STATUSES))

        duration = round(time.time() - cycle_started, 2)
        self.logger.info("Cycle %s finished in %s sec", cycle_number, duration)

    def run_cycle_ingest(self, cycle_number: int):
        cycle_started = time.time()
        self.logger.info("Cycle %s started", cycle_number)

        stage1_result = self._run_stage("Stage 1", lambda: self.pipeline.run_stage1(limit=self.limit))
        if stage1_result is not None and not bool(getattr(stage1_result, "success", True)):
            self.logger.warning(
                "Stage 1 degraded in cycle %s: reason=%s",
                cycle_number,
                getattr(stage1_result, "message", "unknown"),
            )
        stage1_saved = (getattr(stage1_result, "data", {}) or {}).get("saved_new")
        if stage1_saved is not None:
            self.logger.info("Cycle %s new purchases from Stage 1: %s", cycle_number, stage1_saved)

        stage2_probe, stage2_total = self.pipeline.get_stage2_pending_page(offset=0, limit=1)
        if stage2_probe:
            self.logger.info("Stage 2 pending probe: total=%s", stage2_total)
            self._run_stage(
                "Stage 2",
                lambda: self.pipeline.run_stage2(limit=self.limit, overwrite=False),
            )
        else:
            self.logger.info("Stage 2 skipped: no purchases pending Stage 2")

        duration = round(time.time() - cycle_started, 2)
        self.logger.info("Cycle %s finished in %s sec", cycle_number, duration)

    def run_cycle_listing(self, cycle_number: int):
        cycle_started = time.time()
        self.logger.info("Cycle %s started", cycle_number)

        stage3_reg_numbers = self._reg_numbers_by_status(ZakupkaStatus.AI_READY, self.limit)
        if stage3_reg_numbers:
            self._run_stage(
                "Stage 3",
                lambda: self.pipeline.run_stage3(reg_numbers=stage3_reg_numbers, overwrite=False),
            )
        else:
            self.logger.info("Stage 3 skipped: no purchases with status %s", ZakupkaStatus.AI_READY)

        if not self.enable_stage4:
            self.logger.info("Stage 4 disabled by config (WORKER_ENABLE_STAGE4=false)")
        else:
            stage4_reg_numbers = self._reg_numbers_by_statuses(list(STAGE4_QUEUE_STATUSES), self.limit)
            if stage4_reg_numbers:
                self._run_stage4_batch(stage4_reg_numbers)
            else:
                self.logger.info("Stage 4 skipped: no purchases with statuses %s", ",".join(STAGE4_QUEUE_STATUSES))

        duration = round(time.time() - cycle_started, 2)
        self.logger.info("Cycle %s finished in %s sec", cycle_number, duration)

    def run_cycle(self, cycle_number: int):
        if self.mode == self.MODE_INGEST:
            self.run_cycle_ingest(cycle_number)
            return
        if self.mode == self.MODE_LISTING:
            self.run_cycle_listing(cycle_number)
            return
        self.run_cycle_all(cycle_number)

    def run_forever(self, max_cycles: Optional[int] = None) -> int:
        self._install_signal_handlers()

        if not self._acquire_advisory_lock():
            return self.LOCK_BUSY_EXIT_CODE if self._lock_busy else 1

        self.logger.info(
            "Worker started: mode=%s interval=%ss limit=%s top_n=%s details=%s stage4_enabled=%s",
            self.mode,
            self.interval,
            self.limit,
            self.top_n,
            self.get_details,
            self.enable_stage4,
        )

        cycle_number = 0
        try:
            while not self._stop_event.is_set():
                cycle_number += 1
                self.logger.info(
                    "Cron iteration start: ts=%s pid=%s cycle=%s",
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    os.getpid(),
                    cycle_number,
                )
                try:
                    self.run_cycle(cycle_number)
                except Exception:
                    self.logger.exception("Unexpected cycle error")

                if max_cycles and cycle_number >= max_cycles:
                    self.logger.info("Max cycles reached: %s", max_cycles)
                    break

                self.logger.info("Worker sleeping for %s seconds", self.interval)
                self._stop_event.wait(timeout=self.interval)
        finally:
            self._release_advisory_lock()
            self.logger.info("Worker stopped")

        return 0
