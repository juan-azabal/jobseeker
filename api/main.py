from fastapi import FastAPI

app = FastAPI(title="JobSeeker")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
