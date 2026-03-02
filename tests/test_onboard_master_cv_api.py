import json
import pytest
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session, save_master_cv_json
from api.main import app

_MASTER_CV = {
    "version": "1.0",
    "basics": {"name": "Alice Martin", "email": "alice@example.com"},
    "work": [],
    "education": [],
    "skills": [],
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
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c, db_path, user["id"]


def test_get_master_cv_200(authed_client):
    client, db_path, user_id = authed_client
    save_master_cv_json(db_path, user_id, json.dumps(_MASTER_CV))
    resp = client.get("/api/onboard/master-cv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "1.0"
    assert data["basics"]["name"] == "Alice Martin"


def test_get_master_cv_404_when_none(authed_client):
    client, db_path, user_id = authed_client
    resp = client.get("/api/onboard/master-cv")
    assert resp.status_code == 404


def test_get_master_cv_401_unauthenticated():
    c = TestClient(app)
    resp = c.get("/api/onboard/master-cv")
    assert resp.status_code == 401
