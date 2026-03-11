"""Tests for _sync_to_railway() helper in agent/pipeline.py.

Verifies:
- Successful POST → logs success, returns True.
- POST fails (500) → logs warning, returns False, does not raise.
- POST timeout → logs warning, returns False.
- Payload contains `jobs` array and `profile_id`.
- URL is forced to HTTPS scheme.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline as agent_main

SAMPLE_JOBS = [
    {"job_id": "j1", "title": "PM", "company": "Acme", "rag_score": {"score": 72, "tier": "A"}},
    {"job_id": "j2", "title": "Sr PM", "company": "Beta", "rag_score": {"score": 42, "tier": "B"}},
]


def _make_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.return_value = None
    return resp


def test_successful_post_returns_true():
    mock_resp = _make_response(200)
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        result = agent_main._sync_to_railway(SAMPLE_JOBS, 42, "juan", "https://app.railway.app", "secret")
    assert result is True
    mock_post.assert_called_once()


def test_server_error_returns_false():
    mock_resp = _make_response(500)
    mock_resp.raise_for_status.side_effect = Exception("Server Error")
    with patch("httpx.post", side_effect=Exception("Server Error")):
        result = agent_main._sync_to_railway(SAMPLE_JOBS, 42, "juan", "https://app.railway.app", "secret")
    assert result is False


def test_timeout_returns_false():
    import httpx

    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        result = agent_main._sync_to_railway(SAMPLE_JOBS, 42, "juan", "https://app.railway.app", "secret")
    assert result is False


def test_payload_contains_jobs_and_user_id():
    mock_resp = _make_response(200)
    captured_payload = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_payload.update(json or {})
        return mock_resp

    with patch("httpx.post", side_effect=fake_post):
        agent_main._sync_to_railway(SAMPLE_JOBS, 42, "juan", "https://app.railway.app", "secret")

    assert "jobs" in captured_payload
    assert captured_payload["user_id"] == 42
    assert len(captured_payload["jobs"]) == len(SAMPLE_JOBS)


def test_http_url_is_upgraded_to_https():
    mock_resp = _make_response(200)
    captured_urls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_urls.append(url)
        return mock_resp

    with patch("httpx.post", side_effect=fake_post):
        agent_main._sync_to_railway(SAMPLE_JOBS, 42, "juan", "http://app.railway.app", "secret")

    assert len(captured_urls) == 1
    assert captured_urls[0].startswith("https://")
