"""Tests for api/logging_config.py — structured logging configuration.

Test-first per Phase 14 plan: these must FAIL before implementation.
"""

import io
import json

import pytest
import structlog


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog to defaults between tests to avoid cross-test contamination."""
    yield
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------


def test_json_mode_produces_valid_single_line_json():
    """JSON mode outputs valid single-line JSON to the configured stream."""
    from api.logging_config import configure_logging

    buf = io.StringIO()
    configure_logging(json_logs=True, _out=buf)
    logger = structlog.get_logger()
    logger.info("hello json", key="value")

    output = buf.getvalue().strip()
    assert "\n" not in output, "Must be single-line JSON (no newlines in payload)"
    data = json.loads(output)
    assert data["message"] == "hello json"
    assert data["level"] == "info"
    assert "timestamp" in data
    assert data["key"] == "value"


def test_json_mode_warning_level():
    """JSON mode correctly encodes warning level."""
    from api.logging_config import configure_logging

    buf = io.StringIO()
    configure_logging(json_logs=True, _out=buf)
    logger = structlog.get_logger()
    logger.warning("something bad", code=42)

    data = json.loads(buf.getvalue().strip())
    assert data["level"] == "warning"
    assert data["message"] == "something bad"
    assert data["code"] == 42


def test_json_mode_no_event_key():
    """JSON mode uses 'message' not 'event' (Railway compatibility)."""
    from api.logging_config import configure_logging

    buf = io.StringIO()
    configure_logging(json_logs=True, _out=buf)
    structlog.get_logger().info("railway log")

    data = json.loads(buf.getvalue().strip())
    assert "message" in data
    assert "event" not in data  # structlog default key — must be renamed


# ---------------------------------------------------------------------------
# Console mode
# ---------------------------------------------------------------------------


def test_console_mode_produces_non_json():
    """Console mode outputs human-readable text, not JSON."""
    from api.logging_config import configure_logging

    buf = io.StringIO()
    configure_logging(json_logs=False, _out=buf)
    structlog.get_logger().info("hello console")

    output = buf.getvalue()
    assert "hello console" in output
    with pytest.raises((json.JSONDecodeError, ValueError)):
        json.loads(output.strip())


def test_console_mode_contains_level():
    """Console mode output contains the log level."""
    from api.logging_config import configure_logging

    buf = io.StringIO()
    configure_logging(json_logs=False, _out=buf)
    structlog.get_logger().error("boom")

    output = buf.getvalue().lower()
    assert "error" in output


# ---------------------------------------------------------------------------
# Correlation ID header
# ---------------------------------------------------------------------------


def test_correlation_id_header_in_response():
    """Every response includes X-Request-ID header from asgi-correlation-id."""
    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_correlation_id_is_unique_per_request():
    """Each request gets a distinct correlation ID."""
    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        r1 = client.get("/api/health")
        r2 = client.get("/api/health")

    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
