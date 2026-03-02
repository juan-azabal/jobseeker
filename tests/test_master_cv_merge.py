"""Unit tests for shared/master_cv_merge.py — Phase 2.1."""

import pytest
from shared.master_cv_merge import merge_master_cvs, _normalize_company, _dates_overlap

# ---------------------------------------------------------------------------
# _normalize_company
# ---------------------------------------------------------------------------


def test_normalize_strips_ltd():
    assert _normalize_company("Acme Ltd") == "acme"


def test_normalize_strips_inc():
    assert _normalize_company("Tech Inc.") == "tech"


def test_normalize_strips_sl():
    assert _normalize_company("Empresa S.L.") == "empresa"


def test_normalize_strips_gmbh():
    assert _normalize_company("Firma GmbH") == "firma"


def test_normalize_strips_bv():
    assert _normalize_company("Company B.V.") == "company"


def test_normalize_strips_ab():
    assert _normalize_company("Bolaget AB") == "bolaget"


# ---------------------------------------------------------------------------
# _dates_overlap
# ---------------------------------------------------------------------------


def test_dates_overlap_same_period():
    assert _dates_overlap("2020-01", "2022-01", "2020-01", "2022-01") is True


def test_dates_overlap_partial():
    # 2021-01 to 2021-12 = 11 months overlap → True
    assert _dates_overlap("2020-01", "2021-12", "2021-01", "2022-01") is True


def test_dates_no_overlap():
    assert _dates_overlap("2018-01", "2019-01", "2020-01", "2021-01") is False


def test_dates_current_job_overlaps():
    # end_date=None means current job
    assert _dates_overlap("2020-01", None, "2021-01", None) is True


def test_dates_short_overlap_below_min():
    # Only 2 months overlap — below min_months=6
    assert _dates_overlap("2020-01", "2020-03", "2020-02", "2023-01", min_months=6) is False


# ---------------------------------------------------------------------------
# merge_master_cvs — work entries
# ---------------------------------------------------------------------------

_BASE = {
    "version": "1.0",
    "basics": {"name": "Alice", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "Acme",
            "position": "Senior PM",
            "start_date": "2020-01",
            "end_date": None,
            "summary": "Led product.",
            "highlights": ["Increased revenue by 20%"],
            "skills_used": ["python"],
        }
    ],
    "education": [],
    "skills": [{"name": "python"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}


def _incoming_base(**overrides):
    entry = {
        "id": "work_001",
        "company": "Acme",
        "position": "Senior PM",
        "start_date": "2020-01",
        "end_date": None,
        "summary": "Led growth.",
        "highlights": ["Launched new feature X"],
        "skills_used": ["sql"],
    }
    entry.update(overrides)
    return {
        "version": "1.0",
        "basics": {"name": "Alice", "email": "alice@example.com"},
        "work": [entry],
        "education": [],
        "skills": [{"name": "sql"}],
        "languages": [],
        "certifications": [],
        "projects": [],
    }


def test_same_company_overlap_merges():
    merged = merge_master_cvs(_BASE, _incoming_base())
    assert len(merged["work"]) == 1  # merged, not two entries


def test_highlights_merged():
    merged = merge_master_cvs(_BASE, _incoming_base())
    highlights = merged["work"][0]["highlights"]
    assert "Increased revenue by 20%" in highlights
    assert "Launched new feature X" in highlights


def test_duplicate_highlights_deduplicated():
    # Same highlight in both → appears only once
    inc = _incoming_base()
    inc["work"][0]["highlights"] = ["Increased revenue by 20%", "Launched new feature X"]
    merged = merge_master_cvs(_BASE, inc)
    count = merged["work"][0]["highlights"].count("Increased revenue by 20%")
    assert count == 1


def test_different_company_keeps_both():
    inc = _incoming_base(company="OtherCorp", start_date="2015-01", end_date="2018-12")
    merged = merge_master_cvs(_BASE, inc)
    assert len(merged["work"]) == 2


def test_skills_merged_by_name():
    merged = merge_master_cvs(_BASE, _incoming_base())
    names = {s["name"] for s in merged["skills"]}
    assert "python" in names
    assert "sql" in names


def test_skills_no_duplicates():
    # Both have python — should appear once
    inc = _incoming_base()
    inc["skills"] = [{"name": "python"}]
    merged = merge_master_cvs(_BASE, inc)
    python_entries = [s for s in merged["skills"] if s["name"] == "python"]
    assert len(python_entries) == 1


def test_work_ids_reassigned_sequentially():
    """After merge, work entries should have sequential IDs."""
    inc = _incoming_base(company="OtherCorp", start_date="2015-01", end_date="2018-12")
    merged = merge_master_cvs(_BASE, inc)
    ids = [e["id"] for e in merged["work"]]
    assert "work_001" in ids
    assert "work_002" in ids


def test_empty_existing_uses_incoming():
    empty = {**_BASE, "work": [], "skills": []}
    merged = merge_master_cvs(empty, _incoming_base())
    assert len(merged["work"]) == 1
    assert merged["work"][0]["company"] == "Acme"
