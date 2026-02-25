"""Tests for POST /api/onboard/profile/skills (add skill from job detail)."""

import os
import pytest
import yaml
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_user_profile_yaml
from api.main import app


PROFILE_YAML = {
    "user": {
        "name": "Test User",
        "email": "test@test.com",
        "home_locations": ["barcelona"],
        "location_preference": "b",
    },
    "target": {
        "domains": {"data": 15},
        "level": "senior",
        "track": "ic",
    },
    "skills": ["python", "sql"],
}


@pytest.fixture
def authed_client_with_profile(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)

    # Set JOBAGENT_DIR to tmp_path so profile YAML can be written/read
    jobagent_dir = str(tmp_path / "agent")
    monkeypatch.setenv("JOBAGENT_DIR", jobagent_dir)

    # Create profile YAML on disk
    profiles_dir = os.path.join(jobagent_dir, "config", "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    yaml_path = os.path.join(profiles_dir, "testuser.yaml")
    yaml_content = yaml.dump(PROFILE_YAML, default_flow_style=False)
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    # Create user with profile_id
    user = upsert_user(db_path, {
        "google_id": "g_skill", "email": "test@test.com",
        "name": "Test User", "avatar_url": None, "profile_id": "testuser",
    })
    # Store YAML in DB too
    save_user_profile_yaml(db_path, user["id"], yaml_content)
    create_session(db_path, "skill_tok", user["id"], "2099-01-01T00:00:00")

    c = TestClient(app)
    c.cookies.set("jsk", "skill_tok")
    return c, db_path, yaml_path


def test_add_skill_new(authed_client_with_profile):
    client, db_path, yaml_path = authed_client_with_profile
    resp = client.post("/api/onboard/profile/skills", json={"skill": "kafka"})
    assert resp.status_code == 200
    data = resp.json()
    assert "kafka" in data["skills"]
    assert "python" in data["skills"]
    assert "sql" in data["skills"]


def test_add_skill_duplicate_no_error(authed_client_with_profile):
    client, db_path, yaml_path = authed_client_with_profile
    resp = client.post("/api/onboard/profile/skills", json={"skill": "Python"})
    assert resp.status_code == 200
    data = resp.json()
    # Should not add duplicate (python already exists)
    assert data["skills"].count("python") == 1


def test_add_skill_persists_to_yaml(authed_client_with_profile):
    client, db_path, yaml_path = authed_client_with_profile
    client.post("/api/onboard/profile/skills", json={"skill": "kafka"})
    # Verify persisted to YAML file
    with open(yaml_path) as f:
        updated = yaml.safe_load(f)
    assert "kafka" in updated["skills"]


def test_add_skill_persists_to_db(authed_client_with_profile):
    client, db_path, yaml_path = authed_client_with_profile
    from api.db.queries import get_user_profile_yaml
    client.post("/api/onboard/profile/skills", json={"skill": "kafka"})
    # Verify persisted to DB
    stored = get_user_profile_yaml(db_path, 1)
    assert stored is not None
    parsed = yaml.safe_load(stored)
    assert "kafka" in parsed["skills"]


def test_add_skill_unauthenticated():
    c = TestClient(app)
    resp = c.post("/api/onboard/profile/skills", json={"skill": "kafka"})
    assert resp.status_code == 401
