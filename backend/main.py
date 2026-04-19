"""Smart Drone Traffic Analyzer — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import upload, ws
from utils.job_store import recover_stuck_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Recover any jobs that were processing when the server last stopped."""
    recovered = recover_stuck_jobs()
    if recovered:
        print(f"[startup] Recovered {recovered} stuck job(s)")
    yield


app = FastAPI(
    title="Smart Drone Traffic Analyzer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
