"""PostHog analytics singleton.

Provides a no-op mode when POSTHOG_API_KEY is not set so all call-sites
are safe to use unconditionally.

Public API
----------
init_posthog()              — call once at startup
capture(user_id, event, properties)
identify_user(user_id, email, name)
capture_exception(exc, user_id=None)
"""

import atexit
import os

import structlog
from posthog import Posthog

logger = structlog.get_logger(__name__)

_client: Posthog | None = None

# Default to EU Cloud; override via POSTHOG_HOST env var if self-hosting or
# using a different region. Set POSTHOG_HOST=https://us.i.posthog.com for US Cloud.
_DEFAULT_POSTHOG_HOST = "https://eu.i.posthog.com"


def init_posthog() -> None:
    """Initialize the PostHog singleton client.

    No-op when POSTHOG_API_KEY is absent.  Safe to call multiple times
    (only the first call with a key actually creates a client).
    """
    global _client
    api_key = os.environ.get("POSTHOG_API_KEY")
    if not api_key:
        logger.debug("PostHog disabled: POSTHOG_API_KEY not set")
        return

    host = os.environ.get("POSTHOG_HOST", _DEFAULT_POSTHOG_HOST)
    _client = Posthog(
        api_key,
        host=host,
        flush_interval=10,
        enable_exception_autocapture=False,
    )
    atexit.register(_client.shutdown)
    logger.info("PostHog initialized", host=host)


def capture(user_id: int | str, event: str, properties: dict | None = None) -> None:
    """Capture a user event. No-op when PostHog is not configured."""
    if _client is None:
        return
    _client.capture(
        event,
        distinct_id=str(user_id),
        properties=properties or {},
    )


def identify_user(user_id: int | str, email: str, name: str) -> None:
    """Set user properties in PostHog. No-op when PostHog is not configured."""
    if _client is None:
        return
    _client.set(
        distinct_id=str(user_id),
        properties={"email": email, "name": name},
    )


def capture_exception(exc: Exception, user_id: int | str | None = None) -> None:
    """Capture an unhandled exception. No-op when PostHog is not configured."""
    if _client is None:
        return
    kwargs: dict = {}
    if user_id is not None:
        kwargs["distinct_id"] = str(user_id)
    _client.capture_exception(exc, **kwargs)
