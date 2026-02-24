import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)  # Must be before route imports — auth.py reads env vars at module level

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from api.db.init import init_db
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router
from api.routes.onboard import router as onboard_router
from api.routes.ingest import router as ingest_router

app = FastAPI(title="JobSeeker")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-prod"),
    session_cookie="oauth_state",  # rename to avoid clashing with our auth cookie "jsk"
)


@app.on_event("startup")
def on_startup():
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    init_db(db_path)


# --- API routes (must be registered before the SPA catch-all) ---
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(onboard_router)
app.include_router(ingest_router)


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
