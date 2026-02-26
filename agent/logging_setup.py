"""Structlog configuration for the JobAgent pipeline.

Call configure_logging() once at startup (main.py does this automatically).
All other modules can then do:

    import structlog
    logger = structlog.get_logger(__name__)

Output format:
  - JSON  when CI=true or LOG_FORMAT=json (GitHub Actions)
  - Human-readable ConsoleRenderer otherwise (local dev)
"""

import os

import structlog


def configure_logging() -> None:
    """Configure structlog for the agent process.

    Safe to call multiple times — subsequent calls are no-ops if structlog
    is already configured (structlog caches its configuration).
    """
    is_json = os.environ.get("CI") == "true" or os.environ.get("LOG_FORMAT", "").lower() == "json"

    shared_processors = [
        structlog.stdlib.add_log_level,
        # add_logger_name requires stdlib LoggerFactory (has .name attr).
        # We use PrintLoggerFactory, so we skip it here.
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = structlog.processors.JSONRenderer() if is_json else structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
