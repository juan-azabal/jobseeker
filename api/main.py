import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from api.db.init import init_db
from api.routes.jobs import router as jobs_router
from api.routes.auth import router as auth_router

app = FastAPI(title="JobSeeker")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-prod"),
)


@app.on_event("startup")
def on_startup():
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    init_db(db_path)


app.include_router(auth_router)
app.include_router(jobs_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
