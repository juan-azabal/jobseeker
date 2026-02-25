import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Must be before route imports — auth.py reads env vars at module level.
# NOTE: no override=True — Railway env vars must always take precedence over any .env file.

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from api.db.init import init_db
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.routes.onboard import router as onboard_router
from api.routes.ingest import router as ingest_router
from api.routes.admin import router as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SLOW_REQUEST_THRESHOLD_S = 2.0  # log a WARNING for any request taking longer than this

# country_converter logs a WARNING for every city name it can't resolve to a country
# (e.g. "barcelona", "madrid") — expected behaviour for city strings, not an error.
# Silence at WARNING level so our own logs stay readable.
logging.getLogger("country_converter.country_converter").setLevel(logging.ERROR)

app = FastAPI(title="JobSeeker")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-prod"),
    session_cookie="oauth_state",  # rename to avoid clashing with our auth cookie "jsk"
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, status, and duration.

    Emits WARNING for requests exceeding SLOW_REQUEST_THRESHOLD_S so slow
    endpoints are visible in logs without grepping through noise.
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    level = logging.WARNING if elapsed >= SLOW_REQUEST_THRESHOLD_S else logging.DEBUG
    logger.log(
        level,
        "%s %s → %d  (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.on_event("startup")
def on_startup():
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    db_exists = Path(db_path).exists()
    logger.info("=== JobSeeker starting up ===")
    logger.info("DB_PATH=%s  exists=%s", db_path, db_exists)

    # Warn about any critical env vars that are missing
    critical_vars = [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "INGEST_API_KEY",
        "GH_ACTIONS_TOKEN", "GH_REPO",
    ]
    missing = [v for v in critical_vars if not os.environ.get(v)]
    if missing:
        logger.warning("Missing critical env vars: %s", missing)
    else:
        logger.info("All critical env vars present")

    init_db(db_path)
    logger.info("DB ready at %s", db_path)


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
