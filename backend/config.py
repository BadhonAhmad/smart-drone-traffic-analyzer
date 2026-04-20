"""Centralized configuration for the Smart Drone Traffic Analyzer.

All tunable constants live here so that adjusting the pipeline does not
require reading multiple source files.  Values are grouped by concern.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — resolved relative to the backend directory
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent
UPLOAD_DIR = _BASE / "tmp" / "uploads"
OUTPUT_DIR = _BASE / "tmp" / "annotated"
REPORT_DIR = _BASE / "tmp" / "reports"

# ---------------------------------------------------------------------------
# Detection & tracking
# ---------------------------------------------------------------------------
MODEL_NAME = "yolov8n.pt"           # YOLOv8 nano weights (swap to yolov8s for accuracy)
TRACKER = "botsort.yaml"             # BoT-SORT (ReID + motion compensation)
INFERENCE_WIDTH = 640               # Resize frames to this width before inference
FRAME_SKIP = 3                      # Process every Nth frame
COCO_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------
MIN_TRACK_FRAMES = 2                # Frames a track must persist before counted
DEDUP_IOU = 0.3                     # IoU threshold to prevent double-counting same vehicle

# ---------------------------------------------------------------------------
# Annotation colours (BGR for OpenCV)
# ---------------------------------------------------------------------------
CLASS_COLORS = {
    "car": (255, 100, 50),          # blue
    "truck": (50, 50, 255),         # red
    "bus": (50, 255, 255),          # yellow
    "motorcycle": (50, 255, 50),    # green
}

# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".mp4"}
ALLOWED_CONTENT_TYPES = {"video/mp4"}
MP4_MAGIC = b"ftyp"                 # MP4 'ftyp' box at byte offset 4
MAX_UPLOAD_SIZE = 500 * 1024 * 1024 # 500 MB

# ---------------------------------------------------------------------------
# Pipeline behaviour
# ---------------------------------------------------------------------------
PROGRESS_INTERVAL = 30              # Update job store every N processed frames
VIDEO_CODEC = "avc1"                # H.264 — universally supported by browsers

