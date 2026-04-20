"""CV pipeline orchestrator — detection, tracking, counting, annotation, report."""

from __future__ import annotations

import time
import traceback

import cv2
from ultralytics import YOLO

from config import (
    CLASS_COLORS,
    COCO_CLASSES,
    FRAME_SKIP,
    INFERENCE_WIDTH,
    LINE_POSITION,
    MODEL_NAME,
    PROGRESS_INTERVAL,
    OUTPUT_DIR,
    TRACKER,
    UPLOAD_DIR,
    VIDEO_CODEC,
)
from services.annotator import draw_box, draw_counting_line, draw_hud
from services.report import generate_report
from services.scanner import final_scan
from services.tracking import TrackerState
from services.utils import resize
from utils.job_store import update_job

# Ensure directories exist on import
for _d in (UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# DeepSORT is a separate package; import only when needed.
_USE_DEEPSORT = TRACKER == "deepsort"
if _USE_DEEPSORT:
    from deep_sort_realtime.deepsort_tracker import DeepSort
else:
    DeepSort = None  # type: ignore[assignment,misc]


def _init_tracker() -> DeepSort | None:
    """Create a DeepSORT tracker instance (only when TRACKER is "deepsort")."""
    if not _USE_DEEPSORT:
        return None
    return DeepSort(max_age=30, n_init=3, nn_budget=100, embedder="mobilenet")


def _process_frame_builtin(
    model: YOLO,
    inf_frame,
    state: TrackerState,
    frame_idx: int,
    orig_fps: float,
    sx: float, sy: float,
    line_y: float,
    annotated,
    orig_w: int,
) -> None:
    """Run detection + built-in tracker (ByteTrack / BoT-SORT) on one frame."""
    results = model.track(
        inf_frame,
        tracker=TRACKER,
        persist=True,
        classes=list(COCO_CLASSES.keys()),
        verbose=False,
    )

    if not results or results[0].boxes is None:
        return

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

        if state.should_count(tid, cy, line_y, x1, y1, x2, y2):
            state.record(tid, conf, frame_idx, orig_fps, x1, y1, x2, y2, sx, sy)

        state.save_center(tid, cy)
        state.update_position(tid, x1, y1, x2, y2)

        best_cls = state.class_map.get(tid, cls_name)
        color = CLASS_COLORS.get(best_cls, (200, 200, 200))
        draw_box(annotated, tid, best_cls, conf,
                 int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy), color)


def _process_frame_deepsort(
    model: YOLO,
    ds_tracker: DeepSort,
    inf_frame,
    orig_frame,
    state: TrackerState,
    frame_idx: int,
    orig_fps: float,
    sx: float, sy: float,
    line_y: float,
    annotated,
) -> None:
    """Run detection (YOLO) + DeepSORT tracking on one frame."""
    results = model.predict(inf_frame, classes=list(COCO_CLASSES.keys()), verbose=False)
    if not results or results[0].boxes is None:
        return

    raw_dets = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = float(box.conf.item())
        cls_id = int(box.cls.item())
        raw_dets.append(([x1, y1, x2 - x1, y2 - y1], conf, cls_id))

    tracks = ds_tracker.update_tracks(raw_dets, frame=orig_frame)

    for track in tracks:
        if not track.is_confirmed():
            continue

        tid = track.track_id
        ltrb = track.to_ltrb()
        x1, y1, x2, y2 = ltrb
        cy = (y1 + y2) / 2.0

        cls_name = COCO_CLASSES.get(track.get_det_class(), "unknown")
        conf = track.get_det_conf() or 0.0

        state.update_class(tid, cls_name)
        state.bump_frame(tid)

        if state.should_count(tid, cy, line_y, x1, y1, x2, y2):
            state.record(tid, conf, frame_idx, orig_fps, x1, y1, x2, y2, sx, sy)

        state.save_center(tid, cy)
        state.update_position(tid, x1, y1, x2, y2)

        best_cls = state.class_map.get(tid, cls_name)
        color = CLASS_COLORS.get(best_cls, (200, 200, 200))
        draw_box(annotated, tid, best_cls, conf,
                 int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy), color)


def run_pipeline(job_id: str, video_path: str) -> None:
    """Run the full CV pipeline: detect -> track -> count -> annotate -> report."""
    update_job(job_id, status="processing")
    t_start = time.perf_counter()

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            update_job(job_id, status="error", error_message="Cannot open video file")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        update_job(job_id, total_frames=total_frames)

        annotated_path = str(OUTPUT_DIR / f"{job_id}_annotated.mp4")
        fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
        writer = cv2.VideoWriter(annotated_path, fourcc, orig_fps, (orig_w, orig_h))

        model = YOLO(MODEL_NAME)
        ds_tracker = _init_tracker()
        state = TrackerState()
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

                draw_counting_line(annotated, int(line_y * sy), orig_w)

                if _USE_DEEPSORT:
                    _process_frame_deepsort(
                        model, ds_tracker, inf_frame, frame, state,
                        frame_idx, orig_fps, sx, sy, line_y, annotated,
                    )
                else:
                    _process_frame_builtin(
                        model, inf_frame, state,
                        frame_idx, orig_fps, sx, sy, line_y, annotated, orig_w,
                    )

                draw_hud(annotated, state.count, frame_idx)

                if processed % PROGRESS_INTERVAL == 0:
                    pct = round((frame_idx / total_frames) * 100, 1) if total_frames else 0
                    update_job(job_id, processed_frames=frame_idx, progress_pct=pct)

            writer.write(annotated)
            frame_idx += 1

        cap.release()
        writer.release()

        final_scan(
            model, video_path, total_frames,
            orig_w, orig_h, orig_fps, state,
        )

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

        report_path = generate_report(job_id, result_dict, state.detections_log)
        if report_path:
            update_job(job_id, report_path=report_path)

    except Exception:
        tb = traceback.format_exc()
        print(f"[pipeline] Job {job_id} failed:\n{tb}")
        update_job(job_id, status="error", error_message=tb)
