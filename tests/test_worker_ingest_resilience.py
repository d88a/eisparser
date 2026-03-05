from models.stage_result import StageResult
from services.worker_service import WorkerService


class _CollectingLogger:
    def __init__(self):
        self.messages = []

    def _push(self, message, *args):
        if args:
            message = message % args
        self.messages.append(str(message))

    def info(self, message, *args):
        self._push(message, *args)

    def error(self, message, *args):
        self._push(message, *args)

    def exception(self, message, *args):
        self._push(message, *args)

    def warning(self, message, *args):
        self._push(message, *args)


class _FakePipeline:
    def run_stage1(self, limit=10):
        _ = limit
        return StageResult(
            stage=1,
            success=False,
            message="EIS unavailable, retry exhausted",
            errors=["timeout"],
        )

    def get_stage2_pending_page(self, offset=0, limit=1):
        _ = offset, limit
        return [], 0


def test_ingest_cycle_degrades_without_crash_on_stage1_unavailable():
    worker = WorkerService(
        pipeline=_FakePipeline(),
        mode=WorkerService.MODE_INGEST,
        interval=1,
        limit=5,
    )
    logger = _CollectingLogger()
    worker.logger = logger

    worker.run_cycle_ingest(cycle_number=1)

    assert any("Stage 1 finished: success=False" in msg for msg in logger.messages)
    assert any("EIS unavailable, retry exhausted" in msg for msg in logger.messages)
    assert any("Stage 1 errors: ['timeout']" in msg for msg in logger.messages)
    assert any("Stage 1 degraded in cycle 1: reason=EIS unavailable, retry exhausted" in msg for msg in logger.messages)
    assert any("Cycle 1 finished" in msg for msg in logger.messages)
