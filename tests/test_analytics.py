"""Tests for api/analytics.py — PostHog singleton client.

Test-first per Phase 14 plan: must FAIL before implementation.
"""
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_analytics_client():
    """Reset PostHog client between tests to avoid cross-test contamination."""
    import api.analytics as m
    m._client = None
    yield
    m._client = None


# ---------------------------------------------------------------------------
# No-op mode (no POSTHOG_API_KEY)
# ---------------------------------------------------------------------------


def test_capture_noop_without_key():
    from api.analytics import capture
    capture(1, "test_event", {"key": "value"})  # must not raise


def test_identify_noop_without_key():
    from api.analytics import identify_user
    identify_user(1, "test@example.com", "Test User")  # must not raise


def test_capture_exception_noop_without_key():
    from api.analytics import capture_exception
    capture_exception(ValueError("boom"))  # must not raise


def test_init_posthog_noop_without_key():
    """init_posthog() leaves _client as None when POSTHOG_API_KEY is absent."""
    import api.analytics as m
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("POSTHOG_API_KEY", None)
        from api.analytics import init_posthog
        init_posthog()
    assert m._client is None


# ---------------------------------------------------------------------------
# Initialization with key
# ---------------------------------------------------------------------------


def test_init_posthog_registers_atexit():
    """init_posthog() registers posthog.shutdown() with atexit."""
    import api.analytics as m
    mock_client = MagicMock()
    with patch.dict(os.environ, {"POSTHOG_API_KEY": "phc_test_key"}):
        with patch("api.analytics.Posthog", return_value=mock_client):
            with patch("atexit.register") as mock_atexit:
                from api.analytics import init_posthog
                init_posthog()
                mock_atexit.assert_called_once_with(mock_client.shutdown)


def test_init_posthog_autocapture_disabled():
    """PostHog must be initialized with enable_exception_autocapture=False."""
    mock_client = MagicMock()
    with patch.dict(os.environ, {"POSTHOG_API_KEY": "phc_test_key"}):
        with patch("api.analytics.Posthog") as MockPosthog:
            MockPosthog.return_value = mock_client
            from api.analytics import init_posthog
            init_posthog()
            _, kwargs = MockPosthog.call_args
            assert kwargs["enable_exception_autocapture"] is False


def test_init_posthog_flush_interval_10():
    """PostHog must be initialized with flush_interval=10."""
    mock_client = MagicMock()
    with patch.dict(os.environ, {"POSTHOG_API_KEY": "phc_test_key"}):
        with patch("api.analytics.Posthog") as MockPosthog:
            MockPosthog.return_value = mock_client
            from api.analytics import init_posthog
            init_posthog()
            _, kwargs = MockPosthog.call_args
            assert kwargs["flush_interval"] == 10


# ---------------------------------------------------------------------------
# Client call delegation
# ---------------------------------------------------------------------------


def test_capture_calls_client_with_distinct_id():
    """capture() delegates to posthog_client.capture() with distinct_id as str."""
    import api.analytics as m
    m._client = MagicMock()
    from api.analytics import capture
    capture(42, "job_viewed", {"job_id": "abc"})
    m._client.capture.assert_called_once_with(
        "job_viewed",
        distinct_id="42",
        properties={"job_id": "abc"},
    )


def test_identify_user_calls_set():
    """identify_user() uses posthog.set() — the v7.x replacement for identify()."""
    import api.analytics as m
    m._client = MagicMock()
    from api.analytics import identify_user
    identify_user(42, email="x@y.com", name="User X")
    m._client.set.assert_called_once_with(
        distinct_id="42",
        properties={"email": "x@y.com", "name": "User X"},
    )


def test_capture_exception_passes_exc_and_user_id():
    """capture_exception() forwards the exception and distinct_id."""
    import api.analytics as m
    m._client = MagicMock()
    exc = ValueError("boom")
    from api.analytics import capture_exception
    capture_exception(exc, user_id=42)
    call_args = m._client.capture_exception.call_args
    assert call_args[0][0] is exc
    assert call_args[1]["distinct_id"] == "42"


# ---------------------------------------------------------------------------
# Auth callback integration
# ---------------------------------------------------------------------------


def test_auth_callback_calls_identify_user():
    """Auth callback calls identify_user() after successful login."""
    with patch("api.routes.auth.identify_user") as mock_identify:
        with patch("api.routes.auth.upsert_user", return_value={
            "id": 1, "email": "test@example.com", "name": "Test",
            "profile_id": "abc123", "is_admin": 0,
        }):
            with patch("api.routes.auth.create_session"):
                with patch("api.routes.auth.oauth") as mock_oauth:
                    # mock coroutine
                    import asyncio
                    async def fake_token(request):
                        return {"userinfo": {
                            "sub": "g123",
                            "email": "test@example.com",
                            "name": "Test",
                            "picture": None,
                        }}
                    mock_oauth.google.authorize_access_token = fake_token

                    from fastapi.testclient import TestClient
                    from api.main import app
                    with TestClient(app) as client:
                        client.get("/api/auth/callback", follow_redirects=False)

        mock_identify.assert_called_once()


# ---------------------------------------------------------------------------
# 500 exception capture
# ---------------------------------------------------------------------------


def test_unhandled_exception_calls_capture_exception():
    """Unhandled exceptions (500s) are captured via capture_exception()."""
    import asyncio
    import api.analytics as m
    mock_client = MagicMock()
    m._client = mock_client

    from fastapi import Request
    from api.main import unhandled_exception_handler

    # Call the exception handler directly — avoids route-ordering issues when
    # the SPA catch-all (/{full_path:path}) is registered before a dynamic test route.
    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/_test_500"
    exc = RuntimeError("intentional 500 for test")

    response = asyncio.run(unhandled_exception_handler(mock_request, exc))

    assert response.status_code == 500
    mock_client.capture_exception.assert_called_once_with(exc)
