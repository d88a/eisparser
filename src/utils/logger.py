"""Logging utilities for EIS Parser."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str = "eisparser",
    level: int = logging.INFO,
    log_file: Path | None = None,
    use_rotating_file: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    force: bool = False,
    console: bool = True,
) -> logging.Logger:
    """Configure and return logger.

    Args:
        name: Logger name to configure.
        level: Logging level.
        log_file: Optional file path for logs.
        use_rotating_file: Use RotatingFileHandler when True.
        max_bytes: Max log file size before rotation.
        backup_count: Number of rotated files to keep.
        force: Reconfigure logger even if handlers already exist.
        console: Enable stdout logging.
    """
    logger = logging.getLogger(name)

    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    if logger.handlers and not force:
        logger.setLevel(level)
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if use_rotating_file:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return child logger under `eisparser` root."""
    full_name = f"eisparser.{name}" if name else "eisparser"
    logger = logging.getLogger(full_name)

    root = logging.getLogger("eisparser")
    if not root.handlers:
        setup_logger()

    return logger
