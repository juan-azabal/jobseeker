"""Tests for POST /api/onboard/add-entry — Phase 2.6."""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_master_cv_json, get_master_cv_json
from api.main import app

_EXISTING_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice Martin", "email": "alice@example.com"},
    "work": [
        {
            "id": "work_001",
            "company": "Acme",
            "position": "Senior PM",
            "start_date": "2022-01",
            "end_date": None,
            "summary": "Led product.",
            "highlights": [],
            "skills_used": ["python"],
        }
    ],
    "education": [],
    "skills": [{"name": "python"}],
    "languages": [],
    "certifications": [],
    "projects": [],
}


@pytest.fixture
def authed_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    user = upsert_user(
        db_path,
        {
            "google_id": "g_t",
            "email": "t@t.com",
            "name": "T",
            "avatar_url": None,
            "profile_id": "test1234",
        },
    )
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    save_master_cv_json(db_path, user["id"], json.dumps(_EXISTING_MASTER_CV))
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c, db_path, user["id"]


def test_add_work_entry_200(authed_client):
    """Adding a work entry merges it with the existing Master CV."""
    client, db_path, user_id = authed_client
    with patch("api.routes.onboard.index_master_cv"):
        resp = client.post(
            "/api/onboard/add-entry",
            json={
                "type": "work",
                "company": "StartupCo",
                "position": "PM",
                "start_date": "2018-01",
                "end_date": "2021-12",
                "highlights": ["Shipped 5 features"],
                "skills_used": ["sql", "figma"],
                "summary": "B2B SaaS product.",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "master_cv" in data
    assert "entry_id" in data
    companies = [e["company"] for e in data["master_cv"]["work"]]
    assert "StartupCo" in companies
    assert "Acme" in companies


def test_add_project_entry_200(authed_client):
    """Adding a project entry appends it to projects in the Master CV."""
    client, db_path, user_id = authed_client
    with patch("api.routes.onboard.index_master_cv"):
        resp = client.post(
            "/api/onboard/add-entry",
            json={
                "type": "project",
                "name": "Open Source Lib",
                "url": "https://github.com/example/lib",
                "start_date": "2023-01",
                "end_date": "2023-06",
                "highlights": ["500+ stars"],
                "keywords": ["python", "open-source"],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    projects = [p["name"] for p in data["master_cv"]["projects"]]
    assert "Open Source Lib" in projects


def test_add_work_entry_missing_company_422(authed_client):
    """Work entry without company → 422."""
    client, db_path, user_id = authed_client
    resp = client.post(
        "/api/onboard/add-entry",
        json={"type": "work", "position": "PM"},
    )
    assert resp.status_code == 422


def test_add_project_entry_missing_name_422(authed_client):
    """Project entry without name → 422."""
    client, db_path, user_id = authed_client
    resp = client.post(
        "/api/onboard/add-entry",
        json={"type": "project"},
    )
    assert resp.status_code == 422


def test_add_entry_401_unauthenticated():
    c = TestClient(app)
    resp = c.post(
        "/api/onboard/add-entry",
        json={"type": "work", "company": "Foo", "position": "PM"},
    )
    assert resp.status_code == 401
