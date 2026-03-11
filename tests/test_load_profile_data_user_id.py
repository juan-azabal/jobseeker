"""Tests for Phase 2.4: load_profile_data accepts integer user_id, loads from DB.

Replaces the filesystem-based loading approach (profile_id string → YAML file).
The function now reads profile_yaml from the users table via user_id FK.
"""

import sqlite3

import pytest
import yaml

from api.db.init import init_db
from api.db.queries import upsert_user
from api.scoring import load_profile_data


_PROFILE_YAML = yaml.dump(
    {
        "user": {
            "home_locations": ["barcelona"],
            "location_preference": "b",
        },
        "target": {
            "domains": {"saas": 15, "fintech": 10},
            "level": "senior",
            "track": "ic",
            "role_function": "product",
            "role_type": "Senior PM",
        },
        "skills": ["Python", "SQL"],
    }
)


@pytest.fixture()
def db_with_user(tmp_path, monkeypatch):
    """Seeded DB with one user whose profile_yaml is stored. Returns (db_path, user_id)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_lpd",
            "email": "lpd@test.com",
            "name": "LPD User",
            "avatar_url": None,
            "profile_id": "lpduser",
        },
    )
    con = sqlite3.connect(db_path)
    con.execute("UPDATE users SET profile_yaml = ? WHERE id = ?", (_PROFILE_YAML, user["id"]))
    con.commit()
    con.close()
    return db_path, user["id"]


class TestLoadProfileDataUserId:
    def test_loads_from_db_by_user_id(self, db_with_user):
        """load_profile_data(user_id) loads profile from DB, not filesystem."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert profile is not None
        assert "saas" in profile["domains"]
        assert profile["domains"]["saas"] == 15

    def test_none_returns_none(self, db_with_user):
        """load_profile_data(None) returns None — nothing to load."""
        profile = load_profile_data(None)
        assert profile is None

    def test_unknown_user_id_returns_none(self, db_with_user):
        """Non-existent user_id returns None gracefully (no crash)."""
        profile = load_profile_data(99999)
        assert profile is None

    def test_returns_role_function(self, db_with_user):
        """role_function is extracted from target block in DB YAML."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert profile["role_function"] == "product"

    def test_returns_role_type(self, db_with_user):
        """role_type is extracted from target block in DB YAML."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert profile["role_type"] == "Senior PM"

    def test_returns_home_locations(self, db_with_user):
        """home_locations is extracted from user block in DB YAML."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert "barcelona" in profile["home_locations"]

    def test_returns_home_regions(self, db_with_user):
        """home_regions is derived from home_locations (geo module)."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert isinstance(profile["home_regions"], list)

    def test_returns_skills(self, db_with_user):
        """skills list is extracted from top-level YAML."""
        _, uid = db_with_user
        profile = load_profile_data(uid)
        assert "python" in profile["skills"]
        assert "sql" in profile["skills"]

    def test_user_without_profile_yaml_returns_none(self, db_with_user):
        """User with profile_yaml=NULL returns None — not yet onboarded."""
        db_path, _ = db_with_user
        user2 = upsert_user(
            db_path,
            {
                "google_id": "g_lpd2",
                "email": "lpd2@test.com",
                "name": "No YAML",
                "avatar_url": None,
                "profile_id": "noyaml",
            },
        )
        profile = load_profile_data(user2["id"])
        assert profile is None
