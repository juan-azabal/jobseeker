import os
from fastapi import FastAPI
from api.db.init import init_db
from api.routes.jobs import router as jobs_router

app = FastAPI(title="JobSeeker")


@app.on_event("startup")
def on_startup():
    db_path = os.environ.get("DB_PATH", "data/jobseeker.db")
    init_db(db_path)


app.include_router(jobs_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
