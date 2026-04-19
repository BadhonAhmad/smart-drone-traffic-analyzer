"""Upload router — handles video file uploads and triggers processing."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, StreamingResponse

from services.pipeline import run_pipeline, UPLOAD_DIR
from utils.job_store import create_job, get_job

router = APIRouter(prefix="/api")

ALLOWED_CONTENT_TYPES = {"video/mp4"}
ALLOWED_EXTENSIONS = {".mp4"}
# MP4 files have an 'ftyp' box starting at byte offset 4.
MP4_MAGIC = b"ftyp"
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


def _validate_mp4_magic(content: bytes) -> bool:
    """Check whether the first 12 bytes contain the MP4 'ftyp' signature."""
    if len(content) < 12:
        return False
    return content[4:8] == MP4_MAGIC


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, str]:
    """Accept an .mp4 upload, validate it, save to disk, and start processing.

    Validates both the file extension and the MP4 magic bytes (``ftyp`` at
    offset 4).  Returns ``{ "job_id": "<uuid>" }`` immediately while
    processing continues in the background.
    """
    # Extension check
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file. Please upload a valid .mp4 video.",
        )

    content = await file.read()

    # Content-type check
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file. Please upload a valid .mp4 video.",
        )

    # Magic-bytes check
    if not _validate_mp4_magic(content):
        raise HTTPException(
            status_code=400,
            detail="Invalid file. Please upload a valid .mp4 video.",
        )

    job_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{job_id}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)

    dest.write_bytes(content)

    create_job(job_id, str(dest))
    background_tasks.add_task(run_pipeline, job_id, str(dest))

    return {"job_id": job_id}


@router.get("/job/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Return the current status of a processing job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "status": job["status"],
        "progress_pct": job["progress_pct"],
        "total_frames": job["total_frames"],
        "processed_frames": job["processed_frames"],
    }


@router.get("/result/{job_id}")
async def get_result(job_id: str) -> dict:
    """Return the final analysis result for a completed job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job is not complete yet")

    return job["result"]


@router.get("/report/{job_id}")
async def download_report(job_id: str) -> FileResponse:
    """Stream the generated Excel report for download."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job is not complete yet")

    report_path = job.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="File not ready yet.")

    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{job_id}.xlsx",
    )


@router.get("/video/{job_id}", response_model=None)
async def download_video(job_id: str, request: Request) -> StreamingResponse | FileResponse:
    """Stream the annotated output video with HTTP range support for browser playback."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    video_path = job.get("annotated_video_path") or job.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="File not ready yet.")

    file_size = Path(video_path).stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Parse "bytes=start-end"
        range_val = range_header.strip().split("=")[-1]
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def _iter():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            _iter(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Disposition": f"inline; filename=output_{job_id}.mp4",
            },
        )

    # No range header — serve full file
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"output_{job_id}.mp4",
    )
