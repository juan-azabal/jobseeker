"""Tests for 17.6.1 — role_type and role_function returned by load_profile_data.

load_profile_data(user_id: int) must include:
  - role_function: from target.role_function (enum string or None)
  - role_type: from target.role_type (free text string or None)

After Phase 2.4: loads from DB (users.profile_yaml), not filesystem.
"""

import sqlite3

import pytest
import yaml

from api.db.init import init_db
from api.db.queries import upsert_user
from api.scoring import load_profile_data


def _make_profile_yaml(role_function=None, role_type=None) -> str:
    data = {
        "user": {"home_locations": ["london"], "location_preference": "a"},
        "target": {
            "domains": {"saas": 15},
            "level": "senior",
            "track": "ic",
        },
        "skills": ["Python"],
    }
    if role_function is not None:
        data["target"]["role_function"] = role_function
    if role_type is not None:
        data["target"]["role_type"] = role_type
    return yaml.dump(data)


def _seed_user(db_path: str, profile_id: str, profile_yaml: str) -> int:
    """Create a user with stored profile_yaml and return user_id."""
    user = upsert_user(
        db_path,
        {
            "google_id": f"g_{profile_id}",
            "email": f"{profile_id}@test.com",
            "name": profile_id,
            "avatar_url": None,
            "profile_id": profile_id,
        },
    )
    con = sqlite3.connect(db_path)
    con.execute("UPDATE users SET profile_yaml = ? WHERE id = ?", (profile_yaml, user["id"]))
    con.commit()
    con.close()
    return user["id"]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    return db_path


class TestProfileRoleFields:
    def test_role_function_returned(self, db):
        """load_profile_data returns role_function from target block in DB YAML."""
        uid = _seed_user(db, "tu1", _make_profile_yaml(role_function="product"))
        profile = load_profile_data(uid)
        assert profile is not None
        assert profile.get("role_function") == "product"

    def test_role_type_returned(self, db):
        """load_profile_data returns role_type from target block in DB YAML."""
        uid = _seed_user(db, "tu2", _make_profile_yaml(role_type="Head of Product"))
        profile = load_profile_data(uid)
        assert profile is not None
        assert profile.get("role_type") == "Head of Product"

    def test_both_fields_returned(self, db):
        """load_profile_data returns both role_function and role_type."""
        uid = _seed_user(db, "tu3", _make_profile_yaml(role_function="product", role_type="CPO"))
        profile = load_profile_data(uid)
        assert profile is not None
        assert profile["role_function"] == "product"
        assert profile["role_type"] == "CPO"

    def test_missing_fields_return_none(self, db):
        """Profile without role fields returns None for both."""
        uid = _seed_user(db, "tu4", _make_profile_yaml())
        profile = load_profile_data(uid)
        assert profile is not None
        assert profile.get("role_function") is None
        assert profile.get("role_type") is None
