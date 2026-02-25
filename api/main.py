import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Must be before route imports — auth.py reads env vars at module level.
# NOTE: no override=True — Railway env vars must always take precedence over any .env file.

import structlog
from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api.logging_config import configure_logging
from api.db.init import init_db
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.routes.onboard import router as onboard_router
from api.routes.ingest import router as ingest_router
from api.routes.admin import router as admin_router

configure_logging()
logger = structlog.get_logger(__name__)

SLOW_REQUEST_THRESHOLD_MS = 2000.0

# country_converter logs a WARNING for every city name it can't resolve to a country
# (e.g. "barcelona", "madrid") — expected behaviour for city strings, not an error.
# Silence handled inside configure_logging().

app = FastAPI(title="JobSeeker")

# Middleware ordering (first added = outermost per Starlette/FastAPI behaviour):
# 1. SessionMiddleware — reads oauth_state cookie
# 2. CorrelationIdMiddleware — generates UUID per request, sets X-Request-ID header
# 3. structlog_middleware — binds correlation_id + user_id to contextvars, logs request

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-prod"),
    session_cookie="oauth_state",  # rename to avoid clashing with our auth cookie "jsk"
)

app.add_middleware(CorrelationIdMiddleware)


@app.middleware("http")
async def structlog_middleware(request: Request, call_next):
    """Log every request with structured context.

    Binds correlation_id to structlog contextvars so all downstream log calls
    automatically include it. user_id is bound inside get_current_user() for
    protected routes and is included here via contextvars.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id.get(""),
    )

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    log_fn = logger.warning if elapsed_ms >= SLOW_REQUEST_THRESHOLD_MS else logger.info
    log_fn(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=elapsed_ms,
    )
    return response


@app.on_event("startup")
def on_startup():
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    db_exists = Path(db_path).exists()
    logger.info("JobSeeker starting up", db_path=db_path, db_exists=db_exists)

    critical_vars = [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "INGEST_API_KEY",
        "GH_ACTIONS_TOKEN", "GH_REPO",
    ]
    missing = [v for v in critical_vars if not os.environ.get(v)]
    if missing:
        logger.warning("Missing critical env vars", missing=missing)
    else:
        logger.info("All critical env vars present")

    init_db(db_path)
    logger.info("DB ready", db_path=db_path)


# --- API routes (must be registered before the SPA catch-all) ---
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(onboard_router)
app.include_router(ingest_router)
app.include_router(admin_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Static file serving (production SPA) ---
# In dev, web/dist/ doesn't exist — Vite dev server proxies /api to :8000.
# In prod (Docker), web/dist/ contains the built React SPA.

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

if STATIC_DIR.is_dir():
    # Mount hashed asset bundles (JS, CSS) — Vite outputs to dist/assets/
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve React SPA: static files by exact path, index.html for everything else."""
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
