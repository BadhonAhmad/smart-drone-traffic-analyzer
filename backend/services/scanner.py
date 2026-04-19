"""End-of-video final scan to catch late-entering vehicles."""

from __future__ import annotations

import cv2
from ultralytics import YOLO

from services.tracking import COCO_CLASSES, LINE_POSITION, TrackerState
from services.utils import resize


def _iou(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> float:
    """Compute intersection-over-union between two axis-aligned boxes."""
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    a_area = (ax2 - ax1) * (ay2 - ay1)
    b_area = (bx2 - bx1) * (by2 - by1)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0


def final_scan(
    model: YOLO,
    video_path: str,
    total_frames: int,
    orig_w: int,
    orig_h: int,
    orig_fps: float,
    inference_width: int,
    state: TrackerState,
) -> None:
    """Run one detection pass on the last frame and count uncounted vehicles.

    Vehicles in the approach zone (below the counting line) that do not
    overlap with any already-counted vehicle are force-counted. This
    catches vehicles that entered late and never crossed the line.
    """
    if total_frames <= 0:
        return

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    ret, last_frame = cap.read()
    cap.release()
    if not ret:
        return

    inf = resize(last_frame, inference_width)
    inf_h, inf_w = inf.shape[:2]
    line_y = int(inf_h * LINE_POSITION)
    sx = orig_w / inf_w
    sy = orig_h / inf_h

    results = model.predict(inf, classes=list(COCO_CLASSES.keys()), verbose=False)
    if not results or results[0].boxes is None:
        return

    next_fake_id = -1  # negative IDs distinguish final-scan detections

    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        cy = (y1 + y2) / 2.0

        # Only count vehicles in the approach zone (below the line)
        if cy < line_y:
            continue

        cls_id = int(box.cls.item())
        cls_name = COCO_CLASSES.get(cls_id, "unknown")
        conf = float(box.conf.item())

        # Scale to original coordinates
        ox1, oy1 = x1 * sx, y1 * sy
        ox2, oy2 = x2 * sx, y2 * sy

        # IoU dedup: skip if this overlaps a counted vehicle
        if any(
            _iou(ox1, oy1, ox2, oy2, d["x1"], d["y1"], d["x2"], d["y2"]) > 0.3
            for d in state.detections_log
        ):
            continue

        tid = next_fake_id
        next_fake_id -= 1

        state.class_map[tid] = cls_name
        state.seen_ids.add(tid)
        state.detections_log.append({
            "track_id": tid,
            "class_name": cls_name,
            "confidence": round(conf, 4),
            "frame_number": total_frames - 1,
            "timestamp_sec": round((total_frames - 1) / orig_fps, 2),
            "x1": round(ox1, 1),
            "y1": round(oy1, 1),
            "x2": round(ox2, 1),
            "y2": round(oy2, 1),
        })
