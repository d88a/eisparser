#!/usr/bin/env python3
"""EIS Parser CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from config.settings import settings
from pipeline import Pipeline
from services.worker_service import WorkerService
from utils.logger import get_logger, setup_logger


def cmd_stats(pipeline: Pipeline, _args) -> int:
    stats = pipeline.get_statistics()
    print("\nStatistics:")
    print(f"  Purchases: {stats['zakupki']}")
    print(f"  AI results: {stats['ai_results']}")
    print(f"  Listings: {stats['listings']}")
    return 0


def cmd_stage1(pipeline: Pipeline, args) -> int:
    result = pipeline.run_stage1(limit=args.limit)
    print(f"\n{result}")
    if result.errors:
        print(f"  Errors: {result.errors}")
    return 0 if result.success else 1


def cmd_stage2(pipeline: Pipeline, args) -> int:
    result = pipeline.run_stage2(limit=args.limit)
    print(f"\n{result}")
    if result.errors:
        print(f"  Errors: {result.errors}")
    return 0 if result.success else 1


def cmd_stage3(pipeline: Pipeline, args) -> int:
    result = pipeline.run_stage3(limit=args.limit)
    print(f"\n{result}")
    print(f"  Data: {json.dumps(result.data, ensure_ascii=False, indent=2)}")
    if result.errors:
        print(f"  Errors ({len(result.errors)}): {result.errors[:3]}...")
    return 0 if result.success else 1


def cmd_stage4(pipeline: Pipeline, args) -> int:
    result = pipeline.run_stage4(top_n=args.top_n, limit=args.limit, get_details=args.details)
    print(f"\n{result}")
    print(f"  Data: {json.dumps(result.data, ensure_ascii=False, indent=2)}")
    if result.errors:
        print(f"  Errors ({len(result.errors)}): {result.errors[:3]}...")
    return 0 if result.success else 1


def cmd_server(_pipeline: Pipeline | None, args) -> int:
    import uvicorn

    print(f"Starting UI at http://{args.host}:{args.port}")
    reload_enabled = bool(args.reload or settings.server_reload)
    uvicorn.run("api.app:app", host=args.host, port=args.port, reload=reload_enabled)
    return 0


def _run_worker(pipeline: Pipeline, args, mode: str) -> int:
    worker = WorkerService(
        pipeline=pipeline,
        interval=args.interval,
        limit=args.limit,
        top_n=args.top_n,
        get_details=args.details,
        mode=mode,
    )
    max_cycles = args.max_cycles if args.max_cycles and args.max_cycles > 0 else None
    return worker.run_forever(max_cycles=max_cycles)

def cmd_worker(pipeline: Pipeline, args) -> int:
    return _run_worker(pipeline, args, WorkerService.MODE_ALL)


def cmd_worker_ingest(pipeline: Pipeline, args) -> int:
    return _run_worker(pipeline, args, WorkerService.MODE_INGEST)


def cmd_worker_listing(pipeline: Pipeline, args) -> int:
    return _run_worker(pipeline, args, WorkerService.MODE_LISTING)


def _add_common_worker_args(worker_parser):
    worker_parser.add_argument("--interval", type=int, default=300, help="Seconds between cycles")
    worker_parser.add_argument("--limit", type=int, default=10, help="Per-stage purchase limit")
    worker_parser.add_argument("--top-n", type=int, default=10, help="Listings per purchase for Stage 4")
    worker_parser.add_argument("--details", action="store_true", help="Collect building details in Stage 4")
    worker_parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Stop after N cycles (0 = run forever)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EIS Parser CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py stats
  python src/main.py stage1 --limit 10
  python src/main.py stage2 --limit 5
  python src/main.py stage3 --limit 5
  python src/main.py stage4 --top-n 5 --limit 2 --details
  python src/main.py server --host 127.0.0.1 --port 8000 --reload
  python src/main.py worker --interval 300 --limit 10 --top-n 10
  python src/main.py worker-ingest --interval 300 --limit 10
  python src/main.py worker-listing --interval 300 --limit 10 --top-n 10
        """,
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("stats", help="Show statistics")

    stage1_parser = subparsers.add_parser("stage1", help="Stage 1: load purchases")
    stage1_parser.add_argument("--limit", type=int, default=10, help="Max purchases")

    stage2_parser = subparsers.add_parser("stage2", help="Stage 2: AI processing")
    stage2_parser.add_argument("--limit", type=int, default=None, help="Max purchases")

    stage3_parser = subparsers.add_parser("stage3", help="Stage 3: generate 2GIS links")
    stage3_parser.add_argument("--limit", type=int, default=None, help="Max purchases")

    stage4_parser = subparsers.add_parser("stage4", help="Stage 4: collect listings")
    stage4_parser.add_argument("--top-n", type=int, default=20, help="Listings per purchase")
    stage4_parser.add_argument("--limit", type=int, default=None, help="Max purchases")
    stage4_parser.add_argument("--details", action="store_true", help="Collect building details")

    server_parser = subparsers.add_parser("server", help="Run web UI")
    server_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host")
    server_parser.add_argument("--port", type=int, default=8000, help="Port")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")

    worker_parser = subparsers.add_parser("worker", help="Run background Stage 1-4 worker")
    _add_common_worker_args(worker_parser)

    worker_ingest_parser = subparsers.add_parser(
        "worker-ingest",
        help="Run background Stage 1-2 worker",
    )
    _add_common_worker_args(worker_ingest_parser)

    worker_listing_parser = subparsers.add_parser(
        "worker-listing",
        help="Run background Stage 3-4 worker",
    )
    _add_common_worker_args(worker_listing_parser)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    level = logging.DEBUG if args.verbose else logging.INFO

    # Worker has a dedicated rotating log file.
    if args.command in {"worker", "worker-ingest", "worker-listing"}:
        worker_log = Path("results") / "logs" / "worker.log"
        setup_logger(
            level=level,
            log_file=worker_log,
            use_rotating_file=True,
            max_bytes=5 * 1024 * 1024,
            backup_count=5,
            force=True,
        )
    else:
        setup_logger(level=level, force=True)

    logger = get_logger("main")
    logger.debug("CLI args: %s", args)
    fail_fast = (os.getenv("ADMIN_SECURITY_FAIL_FAST", "false").strip().lower() == "true")
    settings.validate_admin_security(fail_fast=fail_fast)

    print("=" * 50)
    print("EIS Parser v2.0")
    print("=" * 50)

    pipeline = None
    if args.command != "server":
        pipeline = Pipeline()
        pipeline.init_database()

    commands = {
        "stats": cmd_stats,
        "stage1": cmd_stage1,
        "stage2": cmd_stage2,
        "stage3": cmd_stage3,
        "stage4": cmd_stage4,
        "server": cmd_server,
        "worker": cmd_worker,
        "worker-ingest": cmd_worker_ingest,
        "worker-listing": cmd_worker_listing,
    }

    cmd = commands.get(args.command)
    if not cmd:
        parser.print_help()
        return 1

    code = cmd(pipeline, args)
    print()
    return int(code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
