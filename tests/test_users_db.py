import pytest
from api.db.init import init_db
from api.db.queries import (
    get_user_by_google_id,
    create_user,
    upsert_user,
    create_session,
    get_session,
    delete_session,
)

USER = {
    "google_id": "g_123",
    "email": "test@example.com",
    "name": "Test User",
    "avatar_url": "https://example.com/avatar.png",
    "profile_id": None,
}


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_create_user_and_get_by_google_id(db_path):
    create_user(db_path, USER)
    user = get_user_by_google_id(db_path, "g_123")
    assert user is not None
    assert user["email"] == "test@example.com"
    assert user["name"] == "Test User"


def test_get_user_not_found(db_path):
    assert get_user_by_google_id(db_path, "nonexistent") is None


def test_upsert_user_creates(db_path):
    upsert_user(db_path, USER)
    user = get_user_by_google_id(db_path, "g_123")
    assert user is not None


def test_upsert_user_updates(db_path):
    create_user(db_path, USER)
    upsert_user(db_path, {**USER, "name": "Updated Name"})
    user = get_user_by_google_id(db_path, "g_123")
    assert user["name"] == "Updated Name"


def test_upsert_user_no_duplicate(db_path):
    upsert_user(db_path, USER)
    upsert_user(db_path, USER)
    import sqlite3
    con = sqlite3.connect(db_path)
    count = con.execute("SELECT COUNT(*) FROM users WHERE google_id = 'g_123'").fetchone()[0]
    assert count == 1


def test_create_and_get_session(db_path):
    create_user(db_path, USER)
    user = get_user_by_google_id(db_path, "g_123")
    create_session(db_path, "tok_abc", user["id"], "2026-12-31T00:00:00")
    session = get_session(db_path, "tok_abc")
    assert session is not None
    assert session["user_id"] == user["id"]


def test_get_session_not_found(db_path):
    assert get_session(db_path, "nonexistent") is None


def test_delete_session(db_path):
    create_user(db_path, USER)
    user = get_user_by_google_id(db_path, "g_123")
    create_session(db_path, "tok_abc", user["id"], "2026-12-31T00:00:00")
    delete_session(db_path, "tok_abc")
    assert get_session(db_path, "tok_abc") is None
