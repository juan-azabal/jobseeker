"""Tests for agent/profile_client.py."""

import pytest
from unittest.mock import patch, MagicMock

from agent.profile_client import fetch_profiles, fetch_profile, fetch_seen_ids, post_seen_ids

RAILWAY_URL = "https://railway.example.com"
INGEST_KEY = "test-key"


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError("", request=MagicMock(), response=resp)
    return resp


# ---------------------------------------------------------------------------
# fetch_profiles
# ---------------------------------------------------------------------------


def test_fetch_profiles_returns_ids():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(
            [
                {"profile_id": "juan", "email": "juan@example.com"},
                {"profile_id": "noura", "email": "noura@example.com"},
            ]
        )
        ids = fetch_profiles(RAILWAY_URL, INGEST_KEY)
    assert ids == ["juan", "noura"]


def test_fetch_profiles_empty():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response([])
        ids = fetch_profiles(RAILWAY_URL, INGEST_KEY)
    assert ids == []


def test_fetch_profiles_http_error_raises():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({}, status_code=403)
        with pytest.raises(RuntimeError, match="HTTP 403"):
            fetch_profiles(RAILWAY_URL, INGEST_KEY)


def test_fetch_profiles_network_error_raises():
    import httpx

    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(RuntimeError, match="network error"):
            fetch_profiles(RAILWAY_URL, INGEST_KEY)


# ---------------------------------------------------------------------------
# fetch_profile
# ---------------------------------------------------------------------------


def test_fetch_profile_returns_parsed_dict():
    yaml_str = "user:\n  name: Noura\nskills:\n  - Python\n"
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({"profile_id": "noura", "profile_yaml": yaml_str})
        profile = fetch_profile(RAILWAY_URL, INGEST_KEY, "noura")
    assert profile["user"]["name"] == "Noura"
    assert "Python" in profile["skills"]


def test_fetch_profile_404_raises():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({"detail": "not found"}, status_code=404)
        with pytest.raises(RuntimeError, match="HTTP 404"):
            fetch_profile(RAILWAY_URL, INGEST_KEY, "ghost")


def test_fetch_profile_network_error_raises():
    import httpx

    with patch("httpx.get", side_effect=httpx.ConnectTimeout("timeout")):
        with pytest.raises(RuntimeError, match="network error"):
            fetch_profile(RAILWAY_URL, INGEST_KEY, "noura")


# ---------------------------------------------------------------------------
# fetch_seen_ids
# ---------------------------------------------------------------------------


def test_fetch_seen_ids_returns_set():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({"profile_id": "juan", "job_ids": ["a", "b", "c"]})
        ids = fetch_seen_ids(RAILWAY_URL, INGEST_KEY, "juan")
    assert ids == {"a", "b", "c"}


def test_fetch_seen_ids_empty():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({"profile_id": "juan", "job_ids": []})
        ids = fetch_seen_ids(RAILWAY_URL, INGEST_KEY, "juan")
    assert ids == set()


def test_fetch_seen_ids_http_error_raises():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response({}, status_code=500)
        with pytest.raises(RuntimeError, match="HTTP 500"):
            fetch_seen_ids(RAILWAY_URL, INGEST_KEY, "juan")


# ---------------------------------------------------------------------------
# post_seen_ids
# ---------------------------------------------------------------------------


def test_post_seen_ids_returns_added_count():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = _mock_response({"added": 3})
        added = post_seen_ids(RAILWAY_URL, INGEST_KEY, "juan", ["x", "y", "z"])
    assert added == 3


def test_post_seen_ids_empty_list_skips_request():
    with patch("httpx.post") as mock_post:
        added = post_seen_ids(RAILWAY_URL, INGEST_KEY, "juan", [])
    mock_post.assert_not_called()
    assert added == 0


def test_post_seen_ids_http_error_raises():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = _mock_response({}, status_code=403)
        with pytest.raises(RuntimeError, match="HTTP 403"):
            post_seen_ids(RAILWAY_URL, INGEST_KEY, "juan", ["x"])


def test_post_seen_ids_network_error_raises():
    import httpx

    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(RuntimeError, match="network error"):
            post_seen_ids(RAILWAY_URL, INGEST_KEY, "juan", ["x"])
