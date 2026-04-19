"""Vehicle tracking state, class mapping, and counting logic."""

from __future__ import annotations

from dataclasses import dataclass, field

# COCO class IDs relevant to traffic analysis
COCO_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Bounding-box colour per class (BGR for OpenCV)
CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "car": (255, 100, 50),        # blue
    "truck": (50, 50, 255),       # red
    "bus": (50, 255, 255),        # yellow
    "motorcycle": (50, 255, 50),  # green
}

# Counting line drawn at 85 % height for visualization.
LINE_POSITION = 0.85

# Minimum processed frames a track must be seen before it is force-counted.
# At FRAME_SKIP=4 this equals ~0.5 seconds — enough to filter flickers
# but short enough to catch every real vehicle.
MIN_TRACK_FRAMES = 3


@dataclass
class TrackerState:
    """Mutable state for one pipeline run — tracking, counting, logging."""

    seen_ids: set[int] = field(default_factory=set)
    class_map: dict[int, str] = field(default_factory=dict)
    class_votes: dict[int, dict[str, int]] = field(default_factory=dict)
    frame_count: dict[int, int] = field(default_factory=dict)
    prev_center_y: dict[int, float] = field(default_factory=dict)
    detections_log: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Class voting
    # ------------------------------------------------------------------
    def update_class(self, tid: int, cls_name: str) -> str:
        """Record a class observation and return the best-voted class."""
        if tid not in self.class_votes:
            self.class_votes[tid] = {}
        self.class_votes[tid][cls_name] = self.class_votes[tid].get(cls_name, 0) + 1
        best = max(self.class_votes[tid], key=self.class_votes[tid].get)  # type: ignore[arg-type]
        self.class_map[tid] = best
        return best

    # ------------------------------------------------------------------
    # Counting decision
    # ------------------------------------------------------------------
    def should_count(self, tid: int, cy: float, line_y: float) -> bool:
        """Decide whether to count this vehicle this frame.

        Two triggers (only evaluated if *tid* is not yet counted):
        1. **Line crossing** — center-Y crossed the line between last frame and now.
        2. **Persistence** — tracked for MIN_TRACK_FRAMES processed frames.
        """
        if tid in self.seen_ids:
            return False

        # Line crossing (early trigger)
        if tid in self.prev_center_y:
            prev = self.prev_center_y[tid]
            if (prev < line_y <= cy) or (prev > line_y >= cy):
                return True

        # Persistence: seen enough frames → definitely a real vehicle
        if self.frame_count.get(tid, 0) >= MIN_TRACK_FRAMES:
            return True

        return False

    # ------------------------------------------------------------------
    # Record a counted vehicle
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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
