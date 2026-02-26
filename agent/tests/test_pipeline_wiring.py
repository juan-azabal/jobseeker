"""
Unit tests for Step 1.5:
_to_dicts() converts list[RawJob] to list[dict] for downstream compatibility.
Checks that main.py merge phase handles RawJob objects correctly.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob


def _make_raw_job(**kwargs) -> RawJob:
    base = dict(id="abc123def456", title="Senior PM", company="Acme", source="indeed")
    base.update(kwargs)
    return RawJob(**base)


class TestToDicts:
    """_to_dicts() converts list[RawJob] → list[dict] for pipeline compatibility."""

    def test_returns_list_of_dicts(self):
        from main import _to_dicts

        jobs = [_make_raw_job()]
        result = _to_dicts(jobs)
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_required_fields_present(self):
        from main import _to_dicts

        result = _to_dicts([_make_raw_job()])[0]
        assert result["id"] == "abc123def456"
        assert result["title"] == "Senior PM"
        assert result["company"] == "Acme"

    def test_is_remote_bool_in_dict(self):
        """is_remote must be a bool in the output dict (prefilter uses it)."""
        from main import _to_dicts

        job = _make_raw_job(remote_type="fulltime")
        result = _to_dicts([job])[0]
        assert result["is_remote"] is True

        job_no = _make_raw_job(remote_type="no")
        result_no = _to_dicts([job_no])[0]
        assert result_no["is_remote"] is False

    def test_none_fields_preserved(self):
        """Optional fields with None are preserved as None (not omitted)."""
        from main import _to_dicts

        job = _make_raw_job(location=None, description=None)
        result = _to_dicts([job])[0]
        assert "location" in result
        assert result["location"] is None

    def test_structured_fields_preserved(self):
        """Structured WTTJ fields (locations_structured, experience_min) are in dict."""
        from main import _to_dicts

        job = _make_raw_job(
            source="wttj",
            remote_type="partial",
            locations_structured=[{"city": "Barcelona", "country_code": "ES"}],
            experience_min=5,
            experience_max=8,
            language="en",
        )
        result = _to_dicts([job])[0]
        assert result["locations_structured"] == [{"city": "Barcelona", "country_code": "ES"}]
        assert result["experience_min"] == 5
        assert result["experience_max"] == 8
        assert result["language"] == "en"

    def test_departments_preserved(self):
        """ATS departments list is preserved."""
        from main import _to_dicts

        job = _make_raw_job(source="greenhouse", departments=["Product"])
        result = _to_dicts([job])[0]
        assert result["departments"] == ["Product"]

    def test_empty_list(self):
        from main import _to_dicts

        assert _to_dicts([]) == []

    def test_multiple_jobs(self):
        from main import _to_dicts

        jobs = [
            _make_raw_job(id="aaa", title="PM 1"),
            _make_raw_job(id="bbb", title="PM 2"),
        ]
        result = _to_dicts(jobs)
        assert len(result) == 2
        assert result[0]["title"] == "PM 1"
        assert result[1]["title"] == "PM 2"
