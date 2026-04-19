"""End-of-video final scan — catches vehicles that were never counted."""

from __future__ import annotations

import cv2
from ultralytics import YOLO

from config import (
    COCO_CLASSES,
    FINAL_SCAN_COUNT,
    FINAL_SCAN_DEDUP_IOU,
    FINAL_SCAN_IOU_MATCH,
    FINAL_SCAN_MIN_FRAMES,
    FINAL_SCAN_SECONDS,
    INFERENCE_WIDTH,
)
from services.tracking import TrackerState
from services.utils import resize


def _iou(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> float:
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def final_scan(
    model: YOLO,
    video_path: str,
    total_frames: int,
    orig_w: int,
    orig_h: int,
    orig_fps: float,
    state: TrackerState,
) -> None:
    """Scan the last ~1 second of video and count uncounted vehicles.

    Runs detection on multiple frames near the end. A vehicle is added
    only if it does not overlap with any already-counted vehicle and is
    seen in at least FINAL_SCAN_MIN_FRAMES of the scanned frames.
    """
    if total_frames <= 0:
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return

    scan_count = min(FINAL_SCAN_COUNT, total_frames)
    frames_back = int(orig_fps * FINAL_SCAN_SECONDS)
    start_frame = max(0, total_frames - frames_back)
    step = max(1, (total_frames - start_frame) // scan_count)
    frame_indices = list(range(start_frame, total_frames, step))
    if not frame_indices:
        frame_indices = [total_frames - 1]

    # Collect detections per frame
    frame_detections: dict[int, list[dict]] = {}

    for fi in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue

        inf = resize(frame, INFERENCE_WIDTH)
        inf_h, inf_w = inf.shape[:2]
        sx, sy = orig_w / inf_w, orig_h / inf_h

        results = model.predict(inf, classes=list(COCO_CLASSES.keys()), verbose=False)
        if not results or results[0].boxes is None:
            continue

        dets = []
        for box in results[0].boxes:
            bx1, by1, bx2, by2 = box.xyxy[0].tolist()
            dets.append({
                "ox1": bx1 * sx, "oy1": by1 * sy,
                "ox2": bx2 * sx, "oy2": by2 * sy,
                "cls": COCO_CLASSES.get(int(box.cls.item()), "unknown"),
                "conf": float(box.conf.item()),
            })
        frame_detections[fi] = dets

    cap.release()
    if not frame_detections:
        return

    # Cluster detections across frames by spatial overlap
    all_dets: list[dict] = []
    for fi, dets in frame_detections.items():
        for d in dets:
            d["frame"] = fi
            all_dets.append(d)

    used: set[int] = set()
    clusters: list[list[dict]] = []

    for i, d in enumerate(all_dets):
        if i in used:
            continue
        cluster = [d]
        used.add(i)
        for j in range(i + 1, len(all_dets)):
            if j in used:
                continue
            other = all_dets[j]
            if d["frame"] == other["frame"]:
                continue
            if _iou(d["ox1"], d["oy1"], d["ox2"], d["oy2"],
                    other["ox1"], other["oy1"], other["ox2"], other["oy2"]) > FINAL_SCAN_IOU_MATCH:
                cluster.append(other)
                used.add(j)
        clusters.append(cluster)

    # Count clusters that appear in enough different frames
    next_fake_id = -1

    for cluster in clusters:
        unique_frames = {d["frame"] for d in cluster}
        if len(unique_frames) < FINAL_SCAN_MIN_FRAMES:
            continue

        best = max(cluster, key=lambda d: d["frame"])
        ox1, oy1, ox2, oy2 = best["ox1"], best["oy1"], best["ox2"], best["oy2"]
        conf = max(d["conf"] for d in cluster)

        # Dedup against already-counted vehicles
        if any(
            _iou(ox1, oy1, ox2, oy2, d["x1"], d["y1"], d["x2"], d["y2"]) > FINAL_SCAN_DEDUP_IOU
            for d in state.detections_log
        ):
            continue

        # Class voting across cluster
        cls_votes: dict[str, int] = {}
        for d in cluster:
            cls_votes[d["cls"]] = cls_votes.get(d["cls"], 0) + 1
        best_cls = max(cls_votes, key=cls_votes.get)  # type: ignore[arg-type]

        tid = next_fake_id
        next_fake_id -= 1

        state.class_map[tid] = best_cls
        state.seen_ids.add(tid)
        state.detections_log.append({
            "track_id": tid,
            "class_name": best_cls,
            "confidence": round(conf, 4),
            "frame_number": best["frame"],
            "timestamp_sec": round(best["frame"] / orig_fps, 2),
            "x1": round(ox1, 1),
            "y1": round(oy1, 1),
            "x2": round(ox2, 1),
            "y2": round(oy2, 1),
        })
