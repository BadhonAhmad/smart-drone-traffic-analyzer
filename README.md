# Smart Drone Traffic Analyzer

## Overview

Smart Drone Traffic Analyzer is a full-stack web application that processes drone surveillance video to detect, track, and count vehicles in real time. It uses YOLOv8 object detection with BoT-SORT multi-object tracking to identify cars, trucks, buses, and motorcycles, then produces an annotated output video and a downloadable Excel report. The frontend streams live progress via WebSocket so users can monitor analysis as it happens.

## Architecture

```
  Browser (Next.js 16)
       |
       |  REST + WebSocket (proxied via Next.js rewrites)
       v
  FastAPI Backend
       |
       +-- BackgroundTask -> run_pipeline()
       |        |
       |        +-- YOLOv8n (object detection)
       |        +-- BoT-SORT (multi-object tracking with ReID)
       |        +-- Persistence counter + spatial dedup
       |        +-- OpenCV (frame annotation + video export)
       |
       +-- report.py -> Excel (.xlsx) generation
```

## Tech Stack

| Layer       | Technology          | Reason                                              |
|-------------|---------------------|------------------------------------------------------|
| Backend     | Python + FastAPI    | Async-native, auto OpenAPI docs, fast development    |
| CV          | Ultralytics YOLOv8n | Lightweight detection with strong COCO pre-training  |
| Tracking    | BoT-SORT            | ReID + motion compensation, handles drone camera shake and occlusions |
| Video I/O   | OpenCV              | Frame-level read/write, drawing, resize              |
| Reports     | openpyxl            | Styled multi-sheet Excel generation                  |
| Frontend    | Next.js 16 (App Router) | Server-proxyable rewrites, React components       |
| Styling     | Tailwind CSS        | Utility-first, dark theme, no external UI library    |
| HTTP Client | Axios               | Typed API helpers, blob download support             |
| Real-time   | WebSocket           | Live progress streaming during video processing      |

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- pip, npm

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### Run Backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Run Both

```bash
# Terminal 1
cd backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Open http://localhost:3000

## How It Works

### CV Pipeline

1. **Upload** — The user drops an `.mp4` file. The backend validates the extension and MP4 magic bytes (`ftyp` at offset 4), saves the file, creates a job, and kicks off a background task.

2. **Detection** — Every 2nd frame is resized to 640 px width and passed through YOLOv8n with BoT-SORT tracking (`classes=[2,3,5,7]` filtering to car, motorcycle, bus, truck).

3. **Counting** — A vehicle is counted once its track ID has persisted for at least 2 processed frames. Before counting, the bounding box is checked against all already-counted vehicles using IoU overlap — if it matches an existing vehicle, it is skipped. This prevents the same physical vehicle from being counted multiple times when the tracker assigns it a new ID.

4. **Annotation** — Every processed frame gets colored bounding boxes (blue=car, red=truck, yellow=bus, green=motorcycle), ID labels, and a HUD overlay showing the running count.

5. **Output** — The annotated video is written via `cv2.VideoWriter` at original resolution and FPS with H.264 encoding for browser playback. An Excel report with three sheets is generated automatically.

### Engineering Decisions

#### Why BoT-SORT over ByteTrack or DeepSORT

Drone footage has inherent camera shake and gradual panning, which causes bounding-box positions to shift even when the vehicle is stationary. Three tracker options were evaluated:

- **ByteTrack**: Uses only bounding-box geometry for association. Fast, but loses track IDs during occlusions and camera movement. No appearance model means ID switches are frequent.
- **DeepSORT**: Adds a ReID appearance model on top of Kalman filtering. Better ID consistency, but lacks camera motion compensation — every frame shift is interpreted as object movement, causing track drift.
- **BoT-SORT** (chosen): Combines ReID appearance features + Kalman filter + camera motion compensation. The motion compensation corrects for drone shake between frames, keeping track IDs stable even when the whole frame shifts. Ranked higher than DeepSORT on MOTChallenge benchmarks and is built into Ultralytics with no extra dependencies.

#### Why persistence-based counting with spatial dedup

Traditional traffic counters use a virtual line and count vehicles when they cross it. This fails in drone footage because:

- Vehicles near the edge of the frame may never cross the line before exiting
- Vehicles that stop (traffic jams, red lights) sit on one side and never cross
- The line position (50%, 85%, etc.) is arbitrary and video-dependent

Instead, every unique track ID that persists for at least 2 processed frames is counted. Additionally, before counting, the bounding box is checked against all already-counted vehicles using IoU (intersection over union). If the overlap exceeds 30%, the track is treated as a duplicate — the same physical vehicle that the tracker reassigned a new ID to — and is skipped. This two-layer approach (persistence + spatial dedup) ensures each vehicle is counted exactly once.

#### Why class voting

YOLO may classify the same vehicle differently across frames (e.g., "truck" in frame 10, "bus" in frame 12). The pipeline tallies every class observation per track ID and uses the most frequent one as the final classification. This turns frame-level noise into a correct aggregate label.

#### Why FRAME_SKIP = 2

At 25 fps, processing every 2nd frame yields ~12.5 inference passes per second. Vehicles in drone footage typically remain in frame for several seconds, giving the tracker enough processed frames to establish and maintain a stable track. Processing every frame would double the processing time with negligible accuracy gain since consecutive frames contain nearly identical information.

#### Why INFERENCE_WIDTH = 640

640 px balances detection accuracy and speed. At 416 px, small or distant vehicles are below the detection threshold of YOLOv8n. At 1280 px, inference is 3-4x slower with diminishing accuracy returns for the typical drone altitude in traffic analysis. 640 px captures vehicles as small as ~20x20 pixels in the input frame.

#### Why YOLOv8n (nano)

The nano model runs ~3x faster than YOLOv8s with acceptable accuracy for vehicle counting. Since the pipeline uses class voting (multiple frames) and spatial dedup as safety nets, occasional misdetections are corrected in aggregate. If higher single-frame accuracy is needed, swapping to `yolov8s.pt` is a one-line change in `config.py`.

#### Why H.264 (`avc1`) codec

Browsers cannot play OpenCV's default `mp4v` codec. H.264 is universally supported in Chrome, Firefox, Safari, and Edge. The annotated video streams directly via `<video>` tag with HTTP range requests (206 Partial Content) for seeking.

#### Why Next.js rewrites instead of CORS

Instead of configuring CORS headers on FastAPI and dealing with preflight requests, the Next.js dev server proxies `/api/*` and `/ws/*` requests to the backend. This means the browser only talks to `localhost:3000` — no cross-origin issues, no preflight overhead. The `proxyClientMaxBodySize: "500mb"` config overrides Next.js's default 10 MB proxy limit to support large video uploads.

#### Why in-memory job store with recovery

The backend is designed as a single-instance service. Job state is stored in a thread-safe Python dict rather than a database, avoiding external dependencies (Redis, PostgreSQL). On server startup, any jobs stuck in "processing" (from a previous crash) are automatically marked as errors. This keeps the setup simple while handling the most common failure mode gracefully.

#### Why centralized config

All tunable constants (model name, tracker, frame skip, inference width, dedup thresholds, colors, upload limits) live in a single `config.py` file. This means adjusting the pipeline never requires reading multiple source files. Swapping the tracker, model, or any threshold is a one-line change.

### Edge Cases Handled

- **Vehicle stops mid-scene** — Persistence counting catches stationary vehicles regardless of position.
- **Tracker reassigns a new ID** — Spatial dedup (IoU check) prevents the same vehicle from being counted twice.
- **Vehicle passes behind occlusion** — BoT-SORT's ReID appearance model re-links tracks after brief disappearances.
- **Camera shake / panning** — BoT-SORT's motion compensation corrects for frame-level shifts.
- **Mislabeled vehicle class** — Class voting across all frames corrects single-frame classification errors.
- **Invalid file upload** — Extension, content-type, and MP4 magic-byte validation reject non-video files.
- **WebSocket disconnect** — Frontend auto-reconnects up to 3 times with a 3-second delay.
- **File too large** — Frontend rejects files over 500 MB before upload.
- **Server crash during processing** — On restart, stuck jobs are automatically detected and marked as failed.

## API Reference

| Method | Endpoint                  | Description                              |
|--------|---------------------------|------------------------------------------|
| POST   | `/api/upload`             | Upload an .mp4 video for analysis        |
| GET    | `/api/job/{job_id}`       | Get current job status and progress      |
| WS     | `/ws/progress/{job_id}`   | Stream real-time progress updates        |
| GET    | `/api/result/{job_id}`    | Get final analysis result JSON           |
| GET    | `/api/report/{job_id}`    | Download Excel report (.xlsx)            |
| GET    | `/api/video/{job_id}`     | Stream annotated output video (.mp4)     |

## Report Format

The generated Excel file contains three sheets:

1. **Detection Log** (shown first) — One row per counting event: track ID, class, confidence, frame number, timestamp, and bounding box coordinates. Alternating white/light-gray rows for readability, auto-fitted column widths.

2. **Summary** — Job ID, total unique vehicles, processing duration, per-type counts, report timestamp. Bold labels with accent-colored header row.

3. **Vehicle Breakdown** — Class, count, and percentage of total for each vehicle type. Centered values with styled header.

## Demo

_Coming soon_
