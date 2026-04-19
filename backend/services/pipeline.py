"""CV pipeline orchestrator — detection, tracking, counting, annotation, report."""

from __future__ import annotations

import time
import traceback
from pathlib import Path

import cv2
from ultralytics import YOLO

from services.annotator import draw_box, draw_counting_line, draw_hud
from services.report import generate_report
from services.scanner import final_scan
from services.tracking import (
    COCO_CLASSES,
    CLASS_COLORS,
    LINE_POSITION,
    TrackerState,
)
from services.utils import resize
from utils.job_store import update_job

# ---------------------------------------------------------------------------
# Directories (absolute paths so CWD doesn't matter)
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent.parent
UPLOAD_DIR = _BASE / "tmp" / "uploads"
OUTPUT_DIR = _BASE / "tmp" / "annotated"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
FRAME_SKIP = 3          # process every 3rd frame
INFERENCE_WIDTH = 640    # higher res = better detection of small/distant vehicles
PROGRESS_INTERVAL = 30  # update job store every N processed frames


def run_pipeline(job_id: str, video_path: str) -> None:
    """Run the full CV pipeline: detect -> track -> count -> annotate -> report."""
    update_job(job_id, status="processing")
    t_start = time.perf_counter()

    try:
        # 1. Open video & gather metadata
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            update_job(job_id, status="error", error_message="Cannot open video file")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        update_job(job_id, total_frames=total_frames)

        # 2. VideoWriter for annotated output (H.264 for browser playback)
        annotated_path = str(OUTPUT_DIR / f"{job_id}_annotated.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        writer = cv2.VideoWriter(annotated_path, fourcc, orig_fps, (orig_w, orig_h))

        # 3. Load model
        model = YOLO("yolov8n.pt")

        # 4. Tracking state
        state = TrackerState()

        # 5. Frame loop
        frame_idx = 0
        processed = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            annotated = frame.copy()

            if frame_idx % FRAME_SKIP == 0:
                processed += 1
                inf_frame = resize(frame, INFERENCE_WIDTH)
                inf_h, inf_w = inf_frame.shape[:2]
                line_y = int(inf_h * LINE_POSITION)
                sx, sy = orig_w / inf_w, orig_h / inf_h

                # Run detection + tracking (BoT-SORT: ReID + motion compensation)
                results = model.track(
                    inf_frame,
                    tracker="botsort.yaml",
                    persist=True,
                    classes=list(COCO_CLASSES.keys()),
                    verbose=False,
                )

                # Draw counting line
                draw_counting_line(annotated, int(line_y * sy), orig_w)

                if results and results[0].boxes is not None:
                    for box in results[0].boxes:
                        tid = int(box.id.item()) if box.id is not None else None
                        if tid is None:
                            continue

                        cls_id = int(box.cls.item())
                        cls_name = COCO_CLASSES.get(cls_id, "unknown")
                        conf = float(box.conf.item())
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        cy = (y1 + y2) / 2.0

                        state.update_class(tid, cls_name)
                        state.bump_frame(tid)

                        if state.should_count(tid, cy, line_y):
                            state.record(
                                tid, conf, frame_idx, orig_fps,
                                x1, y1, x2, y2, sx, sy,
                            )

                        state.save_center(tid, cy)

                        # Draw annotation
                        best_cls = state.class_map.get(tid, cls_name)
                        color = CLASS_COLORS.get(best_cls, (200, 200, 200))
                        draw_box(
                            annotated, tid, best_cls, conf,
                            int(x1 * sx), int(y1 * sy),
                            int(x2 * sx), int(y2 * sy),
                            color,
                        )

                draw_hud(annotated, state.count, frame_idx)

                if processed % PROGRESS_INTERVAL == 0:
                    pct = round((frame_idx / total_frames) * 100, 1) if total_frames else 0
                    update_job(job_id, processed_frames=frame_idx, progress_pct=pct)

            writer.write(annotated)
            frame_idx += 1

        cap.release()
        writer.release()

        # 6. Final scan — catch late-entering vehicles
        final_scan(
            model, video_path, total_frames,
            orig_w, orig_h, orig_fps, INFERENCE_WIDTH, state,
        )

        # 7. Assemble results
        elapsed = round(time.perf_counter() - t_start, 2)
        result_dict = {
            "total_vehicles": state.count,
            "vehicle_breakdown": state.breakdown(),
            "processing_duration_sec": elapsed,
            "job_id": job_id,
        }

        update_job(
            job_id, status="done", progress_pct=100.0,
            processed_frames=frame_idx, result=result_dict,
            annotated_video_path=annotated_path,
        )

        # 8. Generate report
        report_path = generate_report(job_id, result_dict, state.detections_log)
        if report_path:
            update_job(job_id, report_path=report_path)

    except Exception:
        tb = traceback.format_exc()
        print(f"[pipeline] Job {job_id} failed:\n{tb}")
        update_job(job_id, status="error", error_message=tb)
