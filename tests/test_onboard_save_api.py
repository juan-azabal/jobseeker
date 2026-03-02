import json
import os
import yaml
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session, get_user_by_google_id, get_master_cv_json
from api.main import app

PROFILE = {
    "name": "Alice Martin",
    "email": "alice@example.com",
    "languages": ["en", "fr"],
    "home_locations": ["paris", "france"],
    "current_level": "senior",
    "track": "ic",
    "target_level": "principal",
    "domains": {"data": 15, "ml": 10},
    "skills": ["python", "sql"],
    "exclude_companies": ["OldCorp"],
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    jobagent_dir = str(tmp_path / "jobagent")
    os.makedirs(jobagent_dir)
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_t",
            "email": "t@t.com",
            "name": "T",
            "avatar_url": None,
            "profile_id": "test1234",  # pre-assigned at login (new behavior)
        },
    )
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c, tmp_path, db_path


def test_save_profile_200(authed_client):
    client, tmp_path, db_path = authed_client
    resp = client.post(
        "/api/onboard/save-profile",
        json={
            "cv_markdown": "# Alice Martin\n\nSenior PM",
            "profile": PROFILE,
            "salary_min": 80000,
            "location_preference": "b",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "profile_id" in data


def test_save_profile_writes_files(authed_client):
    client, tmp_path, db_path = authed_client
    jobagent_dir = str(tmp_path / "jobagent")
    resp = client.post(
        "/api/onboard/save-profile",
        json={
            "cv_markdown": "# Alice Martin\n\nSenior PM",
            "profile": PROFILE,
            "salary_min": 80000,
            "location_preference": "b",
        },
    )
    # profile_id is pre-assigned at login and returned unchanged by save-profile
    profile_id = resp.json()["profile_id"]
    assert profile_id == "test1234"  # matches what was set in the fixture
    assert os.path.exists(os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml"))
    assert os.path.exists(os.path.join(jobagent_dir, "knowledge", profile_id, "cv.md"))
    assert os.path.exists(os.path.join(jobagent_dir, "config", "seen_ids", f"{profile_id}.txt"))


def test_save_profile_yaml_loadable(authed_client):
    client, tmp_path, db_path = authed_client
    jobagent_dir = str(tmp_path / "jobagent")
    resp = client.post(
        "/api/onboard/save-profile",
        json={
            "cv_markdown": "# Alice Martin\n\nSenior PM",
            "profile": PROFILE,
            "salary_min": 80000,
            "location_preference": "b",
        },
    )
    profile_id = resp.json()["profile_id"]
    yaml_path = os.path.join(jobagent_dir, "config", "profiles", f"{profile_id}.yaml")
    with open(yaml_path) as f:
        loaded = yaml.safe_load(f)
    assert loaded["user"]["id"] == profile_id
    assert loaded["user"]["name"] == "Alice Martin"
    assert loaded["scoring"]["salary_min"] == 80000


def test_save_profile_updates_db(authed_client):
    client, tmp_path, db_path = authed_client
    resp = client.post(
        "/api/onboard/save-profile",
        json={
            "cv_markdown": "# Alice Martin\n\nSenior PM",
            "profile": PROFILE,
            "salary_min": 80000,
            "location_preference": "b",
        },
    )
    expected_profile_id = resp.json()["profile_id"]
    user = get_user_by_google_id(db_path, "g_t")
    assert user["profile_id"] == expected_profile_id


def test_save_profile_unauthenticated():
    c = TestClient(app)
    resp = c.post("/api/onboard/save-profile", json={"cv_markdown": "x", "profile": PROFILE})
    assert resp.status_code == 401


_MASTER_CV_STUB = {
    "version": "1.0",
    "basics": {"name": "Alice Martin", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "Acme",
            "position": "Senior PM",
            "start_date": "2020-01",
            "end_date": None,
            "summary": "Led product.",
            "highlights": ["Shipped feature X"],
            "skills_used": ["python"],
        }
    ],
    "education": [],
    "skills": [],
    "languages": [],
    "certifications": [],
    "projects": [],
}


def test_save_profile_persists_master_cv_json(authed_client):
    """master_cv_json in body must be saved to DB and written to disk (Phase 1.6)."""
    client, tmp_path, db_path = authed_client
    jobagent_dir = str(tmp_path / "jobagent")
    with patch("api.routes.onboard.index_master_cv"):
        resp = client.post(
            "/api/onboard/save-profile",
            json={
                "cv_markdown": "# Alice",
                "profile": PROFILE,
                "master_cv_json": _MASTER_CV_STUB,
            },
        )
    assert resp.status_code == 200
    profile_id = resp.json()["profile_id"]
    # DB must have the JSON stored
    from api.db.queries import get_user_by_google_id as _get_user  # noqa: PLC0415

    user = _get_user(db_path, "g_t")
    stored = get_master_cv_json(db_path, user["id"])
    assert stored is not None
    parsed = json.loads(stored)
    assert parsed["version"] == "1.0"
    assert parsed["basics"]["name"] == "Alice Martin"
    # File must be written to knowledge dir
    json_path = os.path.join(jobagent_dir, "knowledge", profile_id, "master_cv.json")
    assert os.path.exists(json_path)
