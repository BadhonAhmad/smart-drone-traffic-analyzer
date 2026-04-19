"""In-memory job store for tracking video processing job state."""

from __future__ import annotations

import threading
from typing import Any

jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(job_id: str, video_path: str) -> None:
    """Initialize a new job entry in the store."""
    with _lock:
        jobs[job_id] = {
            "status": "pending",
            "progress_pct": 0,
            "processed_frames": 0,
            "total_frames": 0,
            "result": None,
            "report_path": None,
            "video_path": video_path,
            "annotated_video_path": None,
            "error_message": None,
        }


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return a job dict by ID, or None if not found."""
    with _lock:
        return jobs.get(job_id)


def update_job(job_id: str, **fields: Any) -> None:
    """Update specific fields on an existing job."""
    with _lock:
        if job_id in jobs:
            jobs[job_id].update(fields)
