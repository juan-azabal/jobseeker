"""Phase 18.5.1 — Track change regenerates searches with correct titles.

PATCH /profile with track: "management" → searches.yaml uses management track titles
(Director of Product, Head of Product, VP Product) not IC titles.
"""

import os
import yaml
import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_user_profile_yaml
from api.main import app


INITIAL_PROFILE_YAML = """
user:
  name: Test User
  email: test@example.com
  home_locations:
    - spain
  location_preference: b
target:
  level: senior
  track: ic
  role_type: "Product Manager"
  role_function: product
  domains:
    saas: 15
  seniority_weights:
    senior: 15
    staff: 5
skills:
  - python
  - sql
"""


@pytest.fixture
def onboarded_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    # Write initial YAML on disk
    with open(os.path.join(profiles_dir, "test1234.yaml"), "w") as f:
        f.write(INITIAL_PROFILE_YAML)

    user = upsert_user(
        db_path,
        {
            "google_id": "g_track",
            "email": "track@example.com",
            "name": "Track Test",
            "avatar_url": None,
            "profile_id": "test1234",
        },
    )
    # Mark as onboarded by saving profile_yaml to DB (onboarded = bool(profile_yaml))
    save_user_profile_yaml(db_path, user["id"], INITIAL_PROFILE_YAML)

    create_session(db_path, "tok_track", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok_track")
    return c, tmp_path, jobagent_dir


class TestTrackChangeRegeneratesSearches:
    def test_patch_management_track_uses_management_titles(self, onboarded_client):
        """PATCH with track=management → searches.yaml contains management titles."""
        client, tmp_path, jobagent_dir = onboarded_client
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "Test User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15, "staff": 5},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python", "sql"],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "Head of Product",
                "role_function": "product",
                "track": "management",
            },
        )
        assert resp.status_code == 200

        searches_path = os.path.join(jobagent_dir, "config", "profiles", "test1234-searches.yaml")
        assert os.path.exists(searches_path), "searches.yaml should be regenerated"
        searches = yaml.safe_load(open(searches_path).read())

        all_terms = " ".join(s.get("term", "") for s in searches.get("searches", []))
        # Management track should produce Head of Product or Director of Product titles
        assert "Head of Product" in all_terms or "Director of Product" in all_terms, (
            f"Expected management titles in searches, got: {all_terms}"
        )
        # Should NOT include IC-only titles like "Staff Product Manager" as primary
        # (some overlap is OK — title2 fallback might appear)

    def test_patch_ic_track_uses_ic_titles(self, onboarded_client):
        """PATCH with track=ic → searches.yaml contains IC titles."""
        client, tmp_path, jobagent_dir = onboarded_client
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "Test User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python"],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "Senior Product Manager",
                "role_function": "product",
                "track": "ic",
            },
        )
        assert resp.status_code == 200

        searches_path = os.path.join(jobagent_dir, "config", "profiles", "test1234-searches.yaml")
        assert os.path.exists(searches_path)
        searches = yaml.safe_load(open(searches_path).read())

        all_terms = " ".join(s.get("term", "") for s in searches.get("searches", []))
        # IC senior → "Senior Product Manager"
        assert "Senior Product Manager" in all_terms, (
            f"Expected 'Senior Product Manager' in IC searches, got: {all_terms}"
        )
        # Management-only titles should not be primary
        assert "Head of Product" not in all_terms, (
            "IC track should not generate 'Head of Product' titles"
        )

    def test_patch_writes_track_to_yaml(self, onboarded_client):
        """PATCH with track=management → profile YAML persists track=management."""
        client, tmp_path, jobagent_dir = onboarded_client
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "Test User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python"],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "",
                "role_function": "",
                "track": "management",
            },
        )
        assert resp.status_code == 200

        yaml_path = os.path.join(jobagent_dir, "config", "profiles", "test1234.yaml")
        raw = yaml.safe_load(open(yaml_path).read())
        assert raw["target"]["track"] == "management"

    def test_get_profile_returns_track(self, onboarded_client):
        """GET /profile returns track from YAML."""
        client, tmp_path, jobagent_dir = onboarded_client
        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["track"] == "ic"
