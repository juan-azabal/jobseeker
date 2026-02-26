import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.db.init import init_db
from api.db.queries import upsert_user, create_session
from api.main import app


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
            "profile_id": None,
        },
    )
    create_session(db_path, "tok", user["id"], "2099-01-01T00:00:00")
    c = TestClient(app)
    c.cookies.set("jsk", "tok")
    return c


def test_upload_cv_200(authed_client, tmp_path):
    docx_content = b"PK\x03\x04"  # minimal docx-like bytes
    with patch("api.routes.onboard.docx_to_markdown", return_value="# Alice\n\nSenior PM"):
        resp = authed_client.post(
            "/api/onboard/upload-cv",
            files={
                "file": (
                    "cv.docx",
                    io.BytesIO(docx_content),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "markdown" in data
    assert "Alice" in data["markdown"]


def test_upload_cv_pdf_400(authed_client):
    resp = authed_client.post(
        "/api/onboard/upload-cv",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert resp.status_code == 400


def test_upload_cv_too_large_413(authed_client):
    big = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
    resp = authed_client.post(
        "/api/onboard/upload-cv",
        files={"file": ("cv.docx", big, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 413


def test_upload_cv_unauthenticated():
    c = TestClient(app)
    resp = c.post(
        "/api/onboard/upload-cv",
        files={
            "file": (
                "cv.docx",
                io.BytesIO(b"x"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 401
