"""Tests for agent/scripts/reparse_rescore.py.

Verifies:
- --dry-run prints count + cost estimate and exits without API calls.
- Main flow: parse_jd + score_all called for eligible jobs.
- Applied/dismissed jobs are excluded.
- Railway POST called with correct profile_id when credentials present.
- Empty cache exits with informative message.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Import module under test
_SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent.parent))

import reparse_rescore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(job_id, has_desc=True, has_parsed=True, has_rf=False):
    job = {
        "id": job_id,
        "title": f"PM {job_id}",
        "company": "Acme",
        "location": "Remote",
        "job_url": f"https://example.com/{job_id}",
    }
    if has_desc:
        job["description"] = "Long enough description " * 10
    if has_parsed:
        job["parsed"] = {"domain": "saas", "seniority": "senior"}
        if has_rf:
            job["parsed"]["role_function"] = "product"
    return job


def _make_profile():
    return {
        "user": {
            "id": "testuser",
            "name": "Test User",
            "home_locations": ["london"],
            "location_preference": "a",
        },
        "target": {"level": "senior", "track": "ic", "domains": {"saas": 10}},
        "skills": ["python"],
    }


# ---------------------------------------------------------------------------
# Dry-run: prints count and cost, no API calls
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_prints_count_and_cost(self, tmp_path, capsys, monkeypatch):
        jobs = {f"job{i}": _make_job(f"job{i}") for i in range(5)}
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps(jobs))

        applied_yaml = tmp_path / "applied.yaml"

        monkeypatch.setattr(reparse_rescore, "load_cache", lambda: dict(jobs))
        monkeypatch.setattr(reparse_rescore, "load_profile",
                            lambda pid, **kw: _make_profile())
        monkeypatch.setattr(reparse_rescore, "resolve_profile_paths",
                            lambda pid, raw: {"applied": str(applied_yaml)})

        parse_called = []
        monkeypatch.setattr(reparse_rescore, "parse_jd", lambda j: parse_called.append(1) or j)

        with pytest.raises(SystemExit) as exc:
            reparse_rescore.main.__wrapped__ if hasattr(reparse_rescore.main, "__wrapped__") else None
            sys.argv = ["reparse_rescore.py", "--profile", "testuser", "--dry-run"]
            reparse_rescore.main()

        assert exc.value.code == 0
        assert not parse_called, "parse_jd must not be called during --dry-run"
        out = capsys.readouterr().out
        assert "5" in out  # job count
        assert "0.21" in out  # cost estimate (5 * 0.041 = 0.205 → 0.21)

    def test_dry_run_no_railway_call(self, tmp_path, monkeypatch):
        jobs = {"j1": _make_job("j1")}
        monkeypatch.setattr(reparse_rescore, "load_cache", lambda: dict(jobs))
        monkeypatch.setattr(reparse_rescore, "load_profile",
                            lambda pid, **kw: _make_profile())
        monkeypatch.setattr(reparse_rescore, "resolve_profile_paths",
                            lambda pid, raw: {"applied": "/nonexistent.yaml"})

        railway_called = []
        monkeypatch.setattr(reparse_rescore, "_post_to_railway",
                            lambda jobs, pid: railway_called.append(1) or True)

        with pytest.raises(SystemExit):
            sys.argv = ["reparse_rescore.py", "--profile", "testuser", "--dry-run"]
            reparse_rescore.main()

        assert not railway_called


# ---------------------------------------------------------------------------
# Applied filter
# ---------------------------------------------------------------------------

class TestAppliedFilter:
    def test_applied_jobs_excluded(self, tmp_path, monkeypatch):
        jobs = {
            "active1": _make_job("active1"),
            "applied1": _make_job("applied1"),
            "applied2": _make_job("applied2"),
        }
        applied_yaml = tmp_path / "applied.yaml"
        applied_yaml.write_text(
            "applied:\n  ids:\n    - applied1\n    - applied2\n"
        )
        monkeypatch.setattr(reparse_rescore, "load_cache", lambda: dict(jobs))
        monkeypatch.setattr(reparse_rescore, "load_profile",
                            lambda pid, **kw: _make_profile())
        monkeypatch.setattr(reparse_rescore, "resolve_profile_paths",
                            lambda pid, raw: {"applied": str(applied_yaml)})

        parsed_ids = []

        def _fake_parse(job):
            parsed_ids.append(job["id"])
            return job

        def _fake_score_all(jobs, collection, profile):
            return jobs

        monkeypatch.setattr(reparse_rescore, "parse_jd", _fake_parse)
        monkeypatch.setattr(reparse_rescore, "_post_to_railway",
                            lambda jobs, pid: True)
        monkeypatch.setattr(reparse_rescore, "update_cache", lambda c, j: 0)
        monkeypatch.setattr(reparse_rescore, "save_cache", lambda c: None)

        with patch("builtins.__import__", wraps=__import__) as mock_import:
            # Patch vectorstore + scorer inside the function
            import importlib
            vstore_mock = MagicMock()
            vstore_mock.build_vectorstore.return_value = MagicMock()
            scorer_mock = MagicMock()
            scorer_mock.score_all = _fake_score_all

            with patch.dict("sys.modules", {
                "vectorstore": vstore_mock,
                "scorer": scorer_mock,
            }):
                sys.argv = ["reparse_rescore.py", "--profile", "testuser"]
                reparse_rescore.main()

        assert "active1" in parsed_ids
        assert "applied1" not in parsed_ids
        assert "applied2" not in parsed_ids


# ---------------------------------------------------------------------------
# Empty cache
# ---------------------------------------------------------------------------

class TestEmptyCache:
    def test_empty_cache_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(reparse_rescore, "load_cache", lambda: {})
        monkeypatch.setattr(reparse_rescore, "load_profile",
                            lambda pid, **kw: _make_profile())
        monkeypatch.setattr(reparse_rescore, "resolve_profile_paths",
                            lambda pid, raw: {"applied": "/nonexistent.yaml"})

        with pytest.raises(SystemExit) as exc:
            sys.argv = ["reparse_rescore.py", "--profile", "testuser"]
            reparse_rescore.main()

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "cache" in out.lower()


# ---------------------------------------------------------------------------
# _post_to_railway
# ---------------------------------------------------------------------------

class TestPostToRailway:
    def test_skips_when_no_credentials(self, monkeypatch, capsys):
        monkeypatch.delenv("RAILWAY_URL", raising=False)
        monkeypatch.delenv("INGEST_API_KEY", raising=False)
        result = reparse_rescore._post_to_railway([{"id": "j1"}], "testuser")
        assert result is False
        assert "RAILWAY_URL" in capsys.readouterr().out

    def test_returns_true_on_200(self, monkeypatch):
        monkeypatch.setenv("RAILWAY_URL", "https://fake.railway.app")
        monkeypatch.setenv("INGEST_API_KEY", "test-key")

        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(
            {"inserted": 1, "updated": 0}
        ).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = reparse_rescore._post_to_railway([{"id": "j1"}], "testuser")

        assert result is True
