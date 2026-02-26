"""Structured logging configuration using structlog.

Call ``configure_logging()`` once at application startup (api/main.py).

JSON mode (ENVIRONMENT=production): single-line JSON to stdout.
  - Railway reads ``message`` + ``level`` from each line automatically.
  - stderr is treated as errors by Railway — we route everything to stdout.

Console mode (development): human-readable output via ConsoleRenderer.

The ``_out`` parameter is a testing hook; in production always omit it.
"""

import logging
import os
import sys
from typing import IO, Any

import structlog
from structlog.types import EventDict, WrappedLogger


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


def _rename_event_to_message(logger: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """Rename structlog's default 'event' key to 'message' for Railway compatibility."""
    event_dict["message"] = event_dict.pop("event")
    return event_dict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure_logging(
    json_logs: bool | None = None,
    _out: IO[str] | None = None,
) -> None:
    """Configure structlog for the application.

    Args:
        json_logs: True → JSON (production), False → console (dev).
                   Defaults to ``ENVIRONMENT == "production"``.
        _out: Output stream override for testing. Defaults to sys.stdout.
    """
    if json_logs is None:
        json_logs = os.environ.get("ENVIRONMENT", "development") == "production"

    out = _out if _out is not None else sys.stdout

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        processors = shared_processors + [
            _rename_event_to_message,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )

    # Route stdlib logging (uvicorn, libraries) to stdout.
    # Railway classifies stderr as errors — stdlib defaults to stderr.
    logging.basicConfig(
        format="%(message)s",
        stream=out,
        level=logging.INFO,
        force=True,
    )

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("country_converter.country_converter").setLevel(logging.ERROR)
