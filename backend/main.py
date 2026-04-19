"""Smart Drone Traffic Analyzer — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import upload, ws

app = FastAPI(
    title="Smart Drone Traffic Analyzer",
    version="0.1.0",
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
    """Simple health-check endpoint."""
    return {"status": "ok"}
