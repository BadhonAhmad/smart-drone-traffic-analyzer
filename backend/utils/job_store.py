"""Thread-safe in-memory job store."""

from __future__ import annotations

import threading
import time
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(job_id: str, video_path: str) -> None:
    """Initialize a new job entry."""
    with _lock:
        _jobs[job_id] = {
            "status": "pending",
            "progress_pct": 0,
            "processed_frames": 0,
            "total_frames": 0,
            "result": None,
            "report_path": None,
            "video_path": video_path,
            "annotated_video_path": None,
            "error_message": None,
            "created_at": time.time(),
        }


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return a job dict by ID, or None if not found."""
    with _lock:
        return _jobs.get(job_id)


def update_job(job_id: str, **fields: Any) -> None:
    """Update specific fields on an existing job."""
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)
