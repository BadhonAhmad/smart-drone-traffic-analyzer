"""Vehicle tracking state — class mapping, counting logic, and spatial dedup."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import DEDUP_IOU, MIN_TRACK_FRAMES


def _iou(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> float:
    """Intersection-over-union between two axis-aligned boxes."""
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class TrackerState:
    """Mutable state for one pipeline run — tracking, counting, logging."""

    seen_ids: set[int] = field(default_factory=set)
    class_map: dict[int, str] = field(default_factory=dict)
    class_votes: dict[int, dict[str, int]] = field(default_factory=dict)
    frame_count: dict[int, int] = field(default_factory=dict)
    prev_center_y: dict[int, float] = field(default_factory=dict)
    # Last known bounding box per counted vehicle (inference-space coords).
    # Updated every frame so we can catch re-IDs of moving vehicles.
    counted_boxes: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    detections_log: list[dict] = field(default_factory=list)

    def update_class(self, tid: int, cls_name: str) -> str:
        """Record a class observation and return the best-voted class."""
        if tid not in self.class_votes:
            self.class_votes[tid] = {}
        self.class_votes[tid][cls_name] = self.class_votes[tid].get(cls_name, 0) + 1
        best = max(self.class_votes[tid], key=self.class_votes[tid].get)  # type: ignore[arg-type]
        self.class_map[tid] = best
        return best

    def _overlaps_counted(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Check if this box overlaps with any already-counted vehicle."""
        for bx1, by1, bx2, by2 in self.counted_boxes.values():
            if _iou(x1, y1, x2, y2, bx1, by1, bx2, by2) > DEDUP_IOU:
                return True
        return False

    def should_count(self, tid: int, cy: float, line_y: float,
                     x1: float, y1: float, x2: float, y2: float) -> bool:
        """Decide whether to count this vehicle this frame.

        Triggers (only if *tid* is not yet counted and doesn't overlap
        an already-counted vehicle):
        1. Line crossing — center-Y crossed the line since last frame.
        2. Persistence — tracked for MIN_TRACK_FRAMES processed frames.
        """
        if tid in self.seen_ids:
            return False

        # Spatial dedup: same physical vehicle with a new track ID
        if self._overlaps_counted(x1, y1, x2, y2):
            return False

        if tid in self.prev_center_y:
            prev = self.prev_center_y[tid]
            if (prev < line_y <= cy) or (prev > line_y >= cy):
                return True

        if self.frame_count.get(tid, 0) >= MIN_TRACK_FRAMES:
            return True

        return False

    def record(
        self,
        tid: int,
        conf: float,
        frame_idx: int,
        fps: float,
        x1: float, y1: float,
        x2: float, y2: float,
        sx: float, sy: float,
    ) -> dict:
        """Add a counting event to the log and return it."""
        self.seen_ids.add(tid)
        entry = {
            "track_id": tid,
            "class_name": self.class_map.get(tid, "car"),
            "confidence": round(conf, 4),
            "frame_number": frame_idx,
            "timestamp_sec": round(frame_idx / fps, 2),
            "x1": round(x1 * sx, 1),
            "y1": round(y1 * sy, 1),
            "x2": round(x2 * sx, 1),
            "y2": round(y2 * sy, 1),
        }
        self.detections_log.append(entry)
        return entry

    def update_position(self, tid: int, x1: float, y1: float, x2: float, y2: float) -> None:
        """Update last known position for a counted vehicle (inference-space)."""
        if tid in self.seen_ids:
            self.counted_boxes[tid] = (x1, y1, x2, y2)

    def bump_frame(self, tid: int) -> None:
        self.frame_count[tid] = self.frame_count.get(tid, 0) + 1

    def save_center(self, tid: int, cy: float) -> None:
        self.prev_center_y[tid] = cy

    @property
    def count(self) -> int:
        return len(self.seen_ids)

    def breakdown(self) -> dict[str, int]:
        stats = {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0}
        for tid in self.seen_ids:
            cls = self.class_map.get(tid, "car")
            if cls in stats:
                stats[cls] += 1
        return stats
