"""Tests for merge_profiles() pure function — Phase 18.1"""

import pytest
from api.profile_merge import merge_profiles


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def test_skills_union_preserves_order():
    existing = {"skills": ["sql", "python"]}
    extracted = {"skills": ["python", "kafka"]}
    result = merge_profiles(existing, extracted)
    assert result["skills"] == ["sql", "python", "kafka"]


def test_skills_dedup_case_insensitive():
    existing = {"skills": ["SQL"]}
    extracted = {"skills": ["sql", "dbt"]}
    result = merge_profiles(existing, extracted)
    assert result["skills"] == ["SQL", "dbt"]


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------

def test_domains_existing_weights_preserved():
    existing = {"domains": {"saas": 15}}
    extracted = {"domains": {"saas": 12, "fintech": 8}}
    result = merge_profiles(existing, extracted)
    assert result["domains"]["saas"] == 15      # existing wins
    assert result["domains"]["fintech"] == 8    # new domain added


# ---------------------------------------------------------------------------
# Weights — not overwritten
# ---------------------------------------------------------------------------

def test_seniority_weights_not_overwritten():
    existing = {"seniority_weights": {"senior": 15, "staff": 5}}
    extracted = {"seniority_weights": {"senior": 10}}
    result = merge_profiles(existing, extracted)
    assert result["seniority_weights"] == {"senior": 15, "staff": 5}


def test_country_weights_not_overwritten():
    existing = {"country_weights": {"Spain": 10, "Remote": 15}}
    extracted = {"country_weights": {"Spain": 5}}
    result = merge_profiles(existing, extracted)
    assert result["country_weights"] == {"Spain": 10, "Remote": 15}


def test_company_type_weights_not_overwritten():
    existing = {"company_type_weights": {"startup": 15, "enterprise": -5}}
    extracted = {"company_type_weights": {"startup": 5}}
    result = merge_profiles(existing, extracted)
    assert result["company_type_weights"] == {"startup": 15, "enterprise": -5}


# ---------------------------------------------------------------------------
# Factual fields — new CV wins
# ---------------------------------------------------------------------------

def test_name_email_from_new_cv():
    existing = {"name": "Jon", "email": "jon@old.com"}
    extracted = {"name": "Jonathan", "email": "jonathan@new.com"}
    result = merge_profiles(existing, extracted)
    assert result["name"] == "Jonathan"
    assert result["email"] == "jonathan@new.com"


def test_languages_from_new_cv():
    existing = {"languages": ["Spanish"]}
    extracted = {"languages": ["Spanish", "English"]}
    result = merge_profiles(existing, extracted)
    assert result["languages"] == ["Spanish", "English"]


def test_home_locations_from_new_cv():
    existing = {"home_locations": ["Madrid"]}
    extracted = {"home_locations": ["Barcelona", "Remote"]}
    result = merge_profiles(existing, extracted)
    assert result["home_locations"] == ["Barcelona", "Remote"]


# ---------------------------------------------------------------------------
# exclude_companies — union
# ---------------------------------------------------------------------------

def test_exclude_companies_union():
    existing = {"exclude_companies": ["A"]}
    extracted = {"exclude_companies": ["B"]}
    result = merge_profiles(existing, extracted)
    assert result["exclude_companies"] == ["A", "B"]


def test_exclude_companies_union_dedup():
    existing = {"exclude_companies": ["A", "B"]}
    extracted = {"exclude_companies": ["B", "C"]}
    result = merge_profiles(existing, extracted)
    assert result["exclude_companies"] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# role_type, role_function, track — new wins if non-null
# ---------------------------------------------------------------------------

def test_role_type_new_wins_if_present():
    existing = {"role_type": "Product Manager"}
    extracted = {"role_type": "Senior PM"}
    result = merge_profiles(existing, extracted)
    assert result["role_type"] == "Senior PM"


def test_role_type_new_null_preserves_existing():
    existing = {"role_type": "Product Manager"}
    extracted = {"role_type": None}
    result = merge_profiles(existing, extracted)
    assert result["role_type"] == "Product Manager"


def test_role_function_new_wins_if_present():
    existing = {"role_function": "engineering"}
    extracted = {"role_function": "product"}
    result = merge_profiles(existing, extracted)
    assert result["role_function"] == "product"


def test_role_function_new_empty_preserves_existing():
    existing = {"role_function": "engineering"}
    extracted = {"role_function": ""}
    result = merge_profiles(existing, extracted)
    assert result["role_function"] == "engineering"


def test_track_new_wins_if_present():
    existing = {"track": "ic"}
    extracted = {"track": "management"}
    result = merge_profiles(existing, extracted)
    assert result["track"] == "management"


def test_track_new_null_preserves_existing():
    existing = {"track": "management"}
    extracted = {"track": None}
    result = merge_profiles(existing, extracted)
    assert result["track"] == "management"


def test_current_target_level_from_new():
    existing = {"current_level": "senior", "target_level": "staff"}
    extracted = {"current_level": "staff", "target_level": "principal"}
    result = merge_profiles(existing, extracted)
    assert result["current_level"] == "staff"
    assert result["target_level"] == "principal"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_extraction_preserves_all():
    existing = {
        "skills": ["sql"],
        "domains": {"saas": 10},
        "name": "Alice",
        "exclude_companies": ["OldCorp"],
    }
    result = merge_profiles(existing, {})
    assert result["skills"] == ["sql"]
    assert result["domains"] == {"saas": 10}
    assert result["name"] == "Alice"
    assert result["exclude_companies"] == ["OldCorp"]


def test_empty_existing_uses_extraction():
    extracted = {
        "skills": ["python"],
        "domains": {"fintech": 8},
        "name": "Bob",
    }
    result = merge_profiles({}, extracted)
    assert result["skills"] == ["python"]
    assert result["domains"] == {"fintech": 8}
    assert result["name"] == "Bob"
