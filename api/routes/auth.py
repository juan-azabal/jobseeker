import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from api.db.queries import create_session, delete_session, get_session, get_user_by_google_id, upsert_user, set_user_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    "google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)

SESSION_COOKIE = "jsk"
SESSION_TTL_DAYS = 30


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/jobseeker.db")


def _base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000")


def _frontend_url() -> str:
    # In dev, frontend runs on a different port than the API.
    # In prod, leave empty so the redirect falls back to a relative "/".
    return os.environ.get("FRONTEND_URL", "")


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{_base_url()}/api/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}

    email = userinfo.get("email")
    user = upsert_user(_db_path(), {
        "google_id": userinfo.get("sub"),
        "email": email,
        "name": userinfo.get("name"),
        "avatar_url": userinfo.get("picture"),
        "profile_id": None,
    })

    # Auto-promote users whose email is listed in ADMIN_EMAILS env var (idempotent)
    admin_emails = {e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
    if user.get("email") in admin_emails and not user.get("is_admin"):
        set_user_admin(_db_path(), user["id"], True)
        user = {**user, "is_admin": 1}
        logger.info("Admin promoted on login: user_id=%d email=%s", user["id"], email)

    logger.info(
        "Login: user_id=%d email=%s profile_id=%r is_admin=%s",
        user["id"], email, user.get("profile_id"), bool(user.get("is_admin")),
    )

    session_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    create_session(_db_path(), session_token, user["id"], expires_at)

    response = RedirectResponse(url=f"{_frontend_url()}/")
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        secure=_base_url().startswith("https"),
        max_age=SESSION_TTL_DAYS * 86400,
    )
    return response


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        delete_session(_db_path(), token)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/me")
def me(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(_db_path(), token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = get_user_by_google_id(
        _db_path(),
        _get_google_id_by_user_id(_db_path(), session["user_id"]),
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {k: v for k, v in user.items() if k not in ("created_at",)}


def _get_google_id_by_user_id(db_path: str, user_id: int) -> str:
    import sqlite3
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT google_id FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()
    return row["google_id"] if row else ""
