"""Thread-safe in-memory job store with stuck-job recovery."""

from __future__ import annotations

import threading
import time
from typing import Any

from config import STUCK_JOB_TIMEOUT

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


def recover_stuck_jobs() -> int:
    """Mark jobs stuck in "processing" beyond STUCK_JOB_TIMEOUT as errors.

    Called once on server startup.  Returns the number of recovered jobs.
    This handles the case where the server crashes mid-processing — on
    restart those jobs would otherwise remain "processing" forever.
    """
    now = time.time()
    recovered = 0
    with _lock:
        for job_id, job in _jobs.items():
            if job["status"] == "processing":
                age = now - job.get("created_at", now)
                if age > STUCK_JOB_TIMEOUT:
                    job["status"] = "error"
                    job["error_message"] = (
                        f"Job timed out after {STUCK_JOB_TIMEOUT // 60} minutes. "
                        "The server may have restarted during processing."
                    )
                    recovered += 1
    return recovered
