from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Structured logs to stderr (stdout stays clean for CLI output). `fmt`: console or json."""
    level_no = logging.getLevelName(level.upper())
    if not isinstance(level_no, int):
        level_no = logging.INFO
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    logging.basicConfig(
        level=level_no,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def get_logger(name: str = "aikit") -> Any:
    return structlog.get_logger(name)
