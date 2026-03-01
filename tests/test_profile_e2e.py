"""Phase 18.6.2 — End-to-end profile regression tests.

7 scenarios verifying all fields survive all write paths.
"""

import os
import yaml
import pytest
from fastapi.testclient import TestClient

from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_user_profile_yaml
from api.main import app


FULL_PROFILE_YAML = """
user:
  name: E2E User
  email: e2e@example.com
  home_locations:
    - spain
    - remote
  location_preference: b
target:
  level: senior
  track: ic
  role_type: "Senior Product Manager"
  role_function: product
  domains:
    saas: 15
    fintech: 10
  seniority_weights:
    senior: 15
    staff: 5
  country_weights:
    Spain: 10
    Remote: 15
  company_type_weights:
    startup: 10
skills:
  - python
  - sql
  - product analytics
exclude_companies:
  - BigCorp
  - SlowCo
"""


def _make_client(
    tmp_path,
    monkeypatch,
    yaml_content=FULL_PROFILE_YAML,
    google_id="g_e2e",
    email="e2e@example.com",
    session_token="tok_e2e",
    profile_id="e2e_user",
):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    with open(os.path.join(profiles_dir, f"{profile_id}.yaml"), "w") as f:
        f.write(yaml_content)

    user = upsert_user(
        db_path,
        {
            "google_id": google_id,
            "email": email,
            "name": "E2E User",
            "avatar_url": None,
            "profile_id": profile_id,
        },
    )
    save_user_profile_yaml(db_path, user["id"], yaml_content)
    create_session(db_path, session_token, user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", session_token)
    return c, jobagent_dir, profile_id


class TestFullRoundTrip:
    """Scenario 1: GET → PATCH → GET verifies every field persists."""

    def test_get_returns_all_fields(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(tmp_path, monkeypatch)
        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        data = resp.json()["profile"]
        assert data["name"] == "E2E User"
        assert data["email"] == "e2e@example.com"
        assert "spain" in data["home_locations"]
        assert data["role_type"] == "Senior Product Manager"
        assert data["role_function"] == "product"
        assert data["track"] == "ic"
        assert data["domains"]["saas"] == 15
        assert data["seniority_weights"]["senior"] == 15
        assert "python" in data["skills"]
        assert "BigCorp" in data.get("exclude_companies", [])

    def test_patch_all_fields_persists(self, tmp_path, monkeypatch):
        client, jobagent_dir, profile_id = _make_client(tmp_path, monkeypatch)
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "Updated Name",
                "home_locations": ["france"],
                "domains": {"saas": 12, "devtools": 8},
                "seniority_weights": {"senior": 10, "staff": 3},
                "country_weights": {"France": 10},
                "company_type_weights": {"enterprise": 5},
                "skills": ["python", "go"],
                "salary_min": 90000,
                "location_preference": "r",
                "role_type": "Staff PM",
                "role_function": "engineering",
                "track": "management",
            },
        )
        assert resp.status_code == 200

        resp2 = client.get("/api/onboard/profile")
        assert resp2.status_code == 200
        data = resp2.json()["profile"]
        assert data["name"] == "Updated Name"
        assert data["home_locations"] == ["france"]
        assert data["role_type"] == "Staff PM"
        assert data["role_function"] == "engineering"
        assert data["track"] == "management"
        assert data["domains"]["devtools"] == 8
        assert "go" in data["skills"]


class TestRoleFieldsRoundTrip:
    """Scenario 2: role_type + role_function write/read/clear."""

    def test_patch_sets_role_fields(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_role", session_token="tok_role", profile_id="role_user"
        )
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "Role User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python"],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "Head of Product",
                "role_function": "product",
                "track": "management",
            },
        )
        assert resp.status_code == 200

        resp2 = client.get("/api/onboard/profile")
        data = resp2.json()["profile"]
        assert data["role_type"] == "Head of Product"
        assert data["role_function"] == "product"

    def test_patch_empty_role_type_removes_it(self, tmp_path, monkeypatch):
        """Clearing role_type with empty string should remove it from YAML."""
        client, jobagent_dir, profile_id = _make_client(
            tmp_path, monkeypatch, google_id="g_clear", session_token="tok_clear", profile_id="clear_user"
        )
        # First set it
        client.patch(
            "/api/onboard/profile",
            json={
                "name": "E2E User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": [],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "Staff PM",
                "role_function": "engineering",
                "track": "ic",
            },
        )
        # Then clear it
        client.patch(
            "/api/onboard/profile",
            json={
                "name": "E2E User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": [],
                "salary_min": 80000,
                "location_preference": "b",
                "role_type": "",
                "role_function": "",
                "track": "ic",
            },
        )

        yaml_path = os.path.join(jobagent_dir, "config", "profiles", "clear_user.yaml")
        raw = yaml.safe_load(open(yaml_path).read())
        target_block = raw.get("target") or {}
        assert "role_type" not in target_block
        assert "role_function" not in target_block


class TestCVReplaceAdditive:
    """Scenario 3: CV Replace merges additively — skills union, weights preserved."""

    def test_replace_cv_skills_union(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_cv1", session_token="tok_cv1", profile_id="cv1_user"
        )
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "# My CV",
                "extracted_profile": {
                    "skills": ["python", "kafka", "dbt"],
                    "domains": {"saas": 12, "fintech": 8, "data": 10},
                    "name": "E2E User",
                    "email": "e2e@example.com",
                    "home_locations": ["spain"],
                    "seniority_weights": {"senior": 5},  # should be ignored
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        merged_skills = data["merged_profile"]["skills"]
        # Original: python, sql, product analytics; New: python, kafka, dbt
        assert "python" in merged_skills
        assert "sql" in merged_skills  # kept from existing
        assert "kafka" in merged_skills  # added from new
        assert "dbt" in merged_skills  # added from new

    def test_replace_cv_weights_preserved(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_cv2", session_token="tok_cv2", profile_id="cv2_user"
        )
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "",
                "extracted_profile": {
                    "seniority_weights": {"senior": 1, "staff": 1},  # LLM guesses — should be ignored
                    "country_weights": {"Germany": 10},  # should be ignored
                    "domains": {"saas": 5},  # existing saas=15 should win
                },
            },
        )
        assert resp.status_code == 200
        merged = resp.json()["merged_profile"]
        # Existing weights win over extracted
        assert merged["seniority_weights"]["senior"] == 15
        assert merged["seniority_weights"]["staff"] == 5
        assert merged["country_weights"]["Spain"] == 10
        assert merged["domains"]["saas"] == 15  # existing wins

    def test_replace_cv_new_domains_added(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_cv3", session_token="tok_cv3", profile_id="cv3_user"
        )
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "",
                "extracted_profile": {
                    "domains": {"saas": 5, "data": 12},  # data is new
                },
            },
        )
        assert resp.status_code == 200
        merged = resp.json()["merged_profile"]
        assert merged["domains"]["saas"] == 15  # existing wins
        assert merged["domains"]["data"] == 12  # new domain added


class TestCVReplaceMinimalExtraction:
    """Scenario 4: Replace CV where LLM returns minimal data — existing mostly unchanged."""

    def test_empty_extraction_preserves_profile(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_min", session_token="tok_min", profile_id="min_user"
        )
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "Short CV",
                "extracted_profile": {},
            },
        )
        assert resp.status_code == 200
        merged = resp.json()["merged_profile"]
        # All existing data preserved
        assert "python" in merged["skills"]
        assert merged["domains"]["saas"] == 15
        assert merged["seniority_weights"]["senior"] == 15


class TestCVReplacePreservesManualOverrides:
    """Scenario 5: Manually added skills and domains survive CV replace."""

    def test_manual_skills_preserved_after_replace(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_manual", session_token="tok_manual", profile_id="manual_user"
        )
        # Replace CV with completely different skills — manual ones should survive
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "New CV content",
                "extracted_profile": {
                    "skills": ["react", "typescript"],
                    "name": "E2E User",
                },
            },
        )
        assert resp.status_code == 200
        merged = resp.json()["merged_profile"]
        # Original manual skills preserved
        assert "python" in merged["skills"]
        assert "sql" in merged["skills"]
        # New skills also added
        assert "react" in merged["skills"]
        assert "typescript" in merged["skills"]


class TestExcludeCompaniesRoundTrip:
    """Scenario 7: exclude_companies survives all write paths (C5 regression)."""

    def test_exclude_companies_returned_by_get(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_exc", session_token="tok_exc", profile_id="exc_user"
        )
        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        data = resp.json()["profile"]
        assert "BigCorp" in data.get("exclude_companies", [])
        assert "SlowCo" in data.get("exclude_companies", [])

    def test_exclude_companies_survives_patch(self, tmp_path, monkeypatch):
        """PATCH to change name should not lose exclude_companies."""
        client, jobagent_dir, profile_id = _make_client(
            tmp_path, monkeypatch, google_id="g_exc2", session_token="tok_exc2", profile_id="exc2_user"
        )
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "New Name",
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
                "track": "ic",
            },
        )
        assert resp.status_code == 200

        # Verify from API
        resp2 = client.get("/api/onboard/profile")
        data = resp2.json()["profile"]
        assert "BigCorp" in data.get("exclude_companies", [])

        # Verify preferences.yaml was regenerated with exclude_companies
        prefs_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}-preferences.yaml")
        assert os.path.exists(prefs_path), "preferences.yaml should be regenerated"
        prefs = yaml.safe_load(open(prefs_path).read())
        # exclude_companies is nested under prefilter block
        excluded = (prefs.get("prefilter") or {}).get("exclude_companies", [])
        assert "BigCorp" in excluded

    def test_exclude_companies_survives_replace_cv(self, tmp_path, monkeypatch):
        """replace-cv endpoint preserves exclude_companies via merge strategy."""
        client, _, _ = _make_client(
            tmp_path, monkeypatch, google_id="g_exc3", session_token="tok_exc3", profile_id="exc3_user"
        )
        resp = client.patch(
            "/api/onboard/replace-cv",
            json={
                "cv_markdown": "New CV",
                "extracted_profile": {
                    "name": "Different Name",
                    "skills": ["nodejs"],
                },
            },
        )
        assert resp.status_code == 200
        merged = resp.json()["merged_profile"]
        # exclude_companies preserved from existing
        assert "BigCorp" in merged.get("exclude_companies", [])
        assert "SlowCo" in merged.get("exclude_companies", [])


YAML_WITH_SEARCH_TITLES = (
    FULL_PROFILE_YAML
    + """target:
  search_titles:
    - "Senior Product Manager"
    - "Product Owner"
"""
)


class TestSearchTitlesRoundTrip:
    """search_titles: GET returns list, PATCH persists to YAML."""

    def _yaml_with_titles(self):
        return FULL_PROFILE_YAML.replace(
            "  company_type_weights:\n    startup: 10",
            '  company_type_weights:\n    startup: 10\n  search_titles:\n    - "Senior Product Manager"\n    - "Product Owner"',
        )

    def test_get_returns_search_titles(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path,
            monkeypatch,
            yaml_content=self._yaml_with_titles(),
            google_id="g_st1",
            session_token="tok_st1",
            profile_id="st1_user",
        )
        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        titles = resp.json()["profile"].get("search_titles", [])
        assert "Senior Product Manager" in titles
        assert "Product Owner" in titles

    def test_get_returns_empty_list_when_missing(self, tmp_path, monkeypatch):
        client, _, _ = _make_client(
            tmp_path,
            monkeypatch,
            google_id="g_st2",
            session_token="tok_st2",
            profile_id="st2_user",
        )
        resp = client.get("/api/onboard/profile")
        assert resp.status_code == 200
        assert resp.json()["profile"].get("search_titles") == []

    def test_patch_search_titles_persists(self, tmp_path, monkeypatch):
        client, jobagent_dir, profile_id = _make_client(
            tmp_path,
            monkeypatch,
            google_id="g_st3",
            session_token="tok_st3",
            profile_id="st3_user",
        )
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "E2E User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python"],
                "search_titles": ["Senior PM", "Staff PM"],
            },
        )
        assert resp.status_code == 200

        # Verify via GET
        resp2 = client.get("/api/onboard/profile")
        titles = resp2.json()["profile"].get("search_titles", [])
        assert "Senior PM" in titles
        assert "Staff PM" in titles

        # Verify YAML on disk
        yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
        with open(yaml_path) as f:
            raw = yaml.safe_load(f)
        assert raw["target"]["search_titles"] == ["Senior PM", "Staff PM"]

    def test_patch_empty_search_titles_writes_empty_list(self, tmp_path, monkeypatch):
        client, jobagent_dir, profile_id = _make_client(
            tmp_path,
            monkeypatch,
            yaml_content=self._yaml_with_titles(),
            google_id="g_st4",
            session_token="tok_st4",
            profile_id="st4_user",
        )
        resp = client.patch(
            "/api/onboard/profile",
            json={
                "name": "E2E User",
                "home_locations": ["spain"],
                "domains": {"saas": 15},
                "seniority_weights": {"senior": 15},
                "country_weights": {},
                "company_type_weights": {},
                "skills": ["python"],
                "search_titles": [],
            },
        )
        assert resp.status_code == 200

        resp2 = client.get("/api/onboard/profile")
        assert resp2.json()["profile"].get("search_titles") == []
