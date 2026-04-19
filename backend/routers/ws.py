"""WebSocket router — streams real-time progress updates for a job."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils.job_store import get_job

router = APIRouter()

POLL_INTERVAL = 1.0


@router.websocket("/ws/progress/{job_id}")
async def progress_ws(websocket: WebSocket, job_id: str) -> None:
    """Stream JSON progress updates every second until the job completes.

    Each message has the shape:
    ``{ progress_pct, processed_frames, total_frames, status }``

    If the job does not exist a single error message is sent and the
    connection is closed cleanly.
    """
    await websocket.accept()

    # Validate job exists before entering the poll loop
    job = get_job(job_id)
    if not job:
        await websocket.send_json({
            "status": "error",
            "error_message": "Job not found",
        })
        await websocket.close()
        return

    try:
        while True:
            job = get_job(job_id)

            await websocket.send_json({
                "progress_pct": job["progress_pct"],
                "processed_frames": job["processed_frames"],
                "total_frames": job["total_frames"],
                "status": job["status"],
            })

            if job["status"] in ("done", "error"):
                await websocket.close()
                return

            await asyncio.sleep(POLL_INTERVAL)
    except WebSocketDisconnect:
        pass
