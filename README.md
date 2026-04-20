<div align="center">

# Smart Drone Traffic Analyzer

**AI-powered drone video analysis for real-time vehicle detection, tracking, and counting**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-nano-00FFFF?logo=ultralytics&logoColor=black)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Demo Video](#demo) · [Getting Started](#getting-started) · [How It Works](#how-it-works) · [API Reference](#api-reference)

</div>

---

## Overview

Smart Drone Traffic Analyzer is a full-stack web application that processes drone surveillance video to detect, track, and count vehicles in real time. It uses **YOLOv8** object detection with **BoT-SORT** multi-object tracking to identify cars, trucks, buses, and motorcycles, then produces an annotated output video and a downloadable Excel report. The frontend streams live progress via WebSocket so users can monitor analysis as it happens.

### Key Features

- **Drag & drop upload** with file validation (MP4 magic bytes, size limit)
- **Real-time progress** via WebSocket with circular progress indicator
- **Multi-class detection** — cars, trucks, buses, motorcycles
- **Accurate counting** using persistence-based tracking with IoU spatial dedup
- **Class voting** to correct frame-level misclassifications across track lifetime
- **Annotated video output** streamable in-browser with seek support (HTTP range requests)
- **Styled Excel reports** with detection log, summary, and vehicle breakdown sheets
- **Dark-themed responsive UI** built with Tailwind CSS

## Demo

[![Watch the demo video](https://img.shields.io/badge/▶_Watch_Demo_Video-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://drive.google.com/file/d/16c1OZNdno3O3sjHWXF2duAOmO9zwimkk/view?usp=sharing)

> Upload a drone video, watch real-time analysis, and download the results — all in the browser.

## Architecture

```
  Browser (Next.js 16)
       │
       │  REST + WebSocket
       ▼
  FastAPI Backend
       │
       ├─ BackgroundTask → run_pipeline()
       │      │
       │      ├─ YOLOv8n (object detection)
       │      ├─ BoT-SORT (multi-object tracking with ReID)
       │      ├─ Persistence counter + spatial dedup
       │      └─ OpenCV (frame annotation + video export)
       │
       └─ report.py → Excel (.xlsx) generation
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Python + FastAPI | Async-native REST API with auto-generated OpenAPI docs |
| Object Detection | Ultralytics YOLOv8n | Lightweight real-time detection with COCO pre-training |
| Tracking | BoT-SORT | Multi-object tracking with ReID + camera motion compensation |
| Video I/O | OpenCV | Frame-level read/write, annotation drawing, H.264 encoding |
| Reports | openpyxl | Styled multi-sheet Excel generation |
| Frontend | Next.js 16 (App Router) | React-based SPA with server-side API proxying |
| Styling | Tailwind CSS | Utility-first dark theme, no external UI library |
| HTTP Client | Axios | Typed API helpers with blob download support |
| Real-time | WebSocket | Live progress streaming during video processing |

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- pip, npm

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** and drop an `.mp4` drone video to start.

## How It Works

### CV Pipeline

1. **Upload** — The user drops an `.mp4` file. The backend validates the extension and MP4 magic bytes (`ftyp` at offset 4), saves the file, creates a job, and kicks off a background task.

2. **Detection** — Every 2nd frame is resized to 640 px width and passed through YOLOv8n with BoT-SORT tracking (`classes=[2,3,5,7]` filtering to car, motorcycle, bus, truck).

3. **Counting** — A vehicle is counted once its track ID has persisted for at least 2 processed frames. Before counting, the bounding box is checked against all already-counted vehicles using IoU overlap — if it matches an existing vehicle, it is skipped. This prevents the same physical vehicle from being counted multiple times when the tracker assigns it a new ID.

4. **Annotation** — Every processed frame gets colored bounding boxes (blue = car, red = truck, yellow = bus, green = motorcycle), ID labels, and a HUD overlay showing the running count.

5. **Output** — The annotated video is written via `cv2.VideoWriter` at original resolution and FPS with H.264 encoding for browser playback. An Excel report with three sheets is generated automatically.

### Engineering Decisions

#### Why BoT-SORT over ByteTrack or DeepSORT

Drone footage has inherent camera shake and gradual panning, which causes bounding-box positions to shift even when the vehicle is stationary.

- **ByteTrack** — Uses only bounding-box geometry for association. Fast, but loses track IDs during occlusions and camera movement. No appearance model means frequent ID switches.
- **DeepSORT** — Adds a ReID appearance model on top of Kalman filtering. Better ID consistency, but lacks camera motion compensation — every frame shift is interpreted as object movement, causing track drift.
- **BoT-SORT** (chosen) — Combines ReID appearance features + Kalman filter + camera motion compensation. Ranked higher than DeepSORT on MOTChallenge benchmarks and is built into Ultralytics with no extra dependencies.

#### Why persistence-based counting with spatial dedup

Traditional traffic counters use a virtual line and count vehicles when they cross it. This fails in drone footage because:

- Vehicles near the edge of the frame may never cross the line before exiting
- Vehicles that stop (traffic jams, red lights) sit on one side and never cross
- The line position is arbitrary and video-dependent

Instead, every unique track ID that persists for at least 2 processed frames is counted. Additionally, before counting, the bounding box is checked against all already-counted vehicles using IoU (intersection over union). If the overlap exceeds 30%, the track is treated as a duplicate — the same physical vehicle that the tracker reassigned a new ID to — and is skipped.

#### Why class voting

YOLO may classify the same vehicle differently across frames (e.g., "truck" in frame 10, "bus" in frame 12). The pipeline tallies every class observation per track ID and uses the most frequent one as the final classification. This turns frame-level noise into a correct aggregate label.

#### Why FRAME_SKIP = 2

At 25 fps, processing every 2nd frame yields ~12.5 inference passes per second. Vehicles in drone footage typically remain in frame for several seconds, giving the tracker enough processed frames to establish and maintain a stable track. Processing every frame would double the processing time with negligible accuracy gain.

#### Why INFERENCE_WIDTH = 640

640 px balances detection accuracy and speed. At 416 px, small or distant vehicles are below the detection threshold. At 1280 px, inference is 3-4x slower with diminishing returns. 640 px captures vehicles as small as ~20x20 pixels.

#### Why YOLOv8n (nano)

The nano model runs ~3x faster than YOLOv8s with acceptable accuracy for vehicle counting. Since the pipeline uses class voting and spatial dedup as safety nets, occasional misdetections are corrected in aggregate. Swapping to `yolov8s.pt` is a one-line change in `config.py`.

#### Why H.264 (`avc1`) codec

Browsers cannot play OpenCV's default `mp4v` codec. H.264 is universally supported in Chrome, Firefox, Safari, and Edge. The annotated video streams directly via `<video>` tag with HTTP range requests (206 Partial Content) for seeking.

#### Why centralized config

All tunable constants (model name, tracker, frame skip, inference width, dedup thresholds, colors, upload limits) live in a single `config.py` file. Swapping the tracker, model, or any threshold is a one-line change — no need to read multiple source files.

### Edge Cases Handled

| Scenario | Solution |
|----------|----------|
| Vehicle stops mid-scene | Persistence counting catches stationary vehicles regardless of position |
| Tracker reassigns a new ID | IoU-based spatial dedup prevents double-counting |
| Vehicle passes behind occlusion | BoT-SORT's ReID model re-links tracks after brief disappearances |
| Camera shake / panning | BoT-SORT's motion compensation corrects for frame-level shifts |
| Mislabeled vehicle class | Class voting across all frames corrects single-frame errors |
| Invalid file upload | Extension, content-type, and MP4 magic-byte validation |
| WebSocket disconnect | Frontend auto-reconnects up to 3 times with 3-second delay |
| File too large | Frontend rejects files over 500 MB before upload |

## Project Structure

```
smart-drone-traffic-analyzer/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # All tunable constants
│   ├── requirements.txt
│   ├── routers/
│   │   ├── upload.py            # Upload, job status, video streaming, report download
│   │   └── ws.py                # WebSocket progress endpoint
│   ├── services/
│   │   ├── pipeline.py          # CV pipeline orchestrator
│   │   ├── tracking.py          # TrackerState — counting logic + spatial dedup
│   │   ├── annotator.py         # OpenCV drawing helpers
│   │   ├── report.py            # Styled Excel report generation
│   │   └── utils.py             # Shared utilities (resize)
│   └── utils/
│       └── job_store.py         # Thread-safe in-memory job store
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Root layout with metadata
│   │   │   └── page.tsx         # Main page — state machine (upload → processing → results)
│   │   └── components/
│   │       ├── UploadZone.tsx   # Drag & drop with file validation
│   │       ├── ProgressScreen.tsx # Real-time progress with stop button
│   │       ├── ResultsDashboard.tsx # Video player, stats, download buttons
│   │       └── ErrorCard.tsx    # Error display with retry
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── .gitignore
└── README.md
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload an `.mp4` video for analysis |
| `GET` | `/api/job/{job_id}` | Get current job status and progress |
| `WS` | `/ws/progress/{job_id}` | Stream real-time progress updates |
| `GET` | `/api/result/{job_id}` | Get final analysis result JSON |
| `GET` | `/api/report/{job_id}` | Download Excel report (`.xlsx`) |
| `GET` | `/api/video/{job_id}` | Stream annotated output video (`.mp4`) |
| `GET` | `/api/health` | Health check endpoint |

## Report Format

The generated Excel file contains three sheets:

1. **Detection Log** — One row per counting event: track ID, class, confidence, frame number, timestamp, and bounding box coordinates. Alternating white/light-gray rows, auto-fitted columns.

2. **Summary** — Job ID, total unique vehicles, processing duration, per-type counts, and report timestamp. Bold labels with accent-colored header row.

3. **Vehicle Breakdown** — Class, count, and percentage of total for each vehicle type. Centered values with styled header.

## Configuration

All settings are centralized in `backend/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MODEL_NAME` | `yolov8n.pt` | YOLO model weights (swap to `yolov8s.pt` for accuracy) |
| `TRACKER` | `botsort.yaml` | Tracker config (`botsort.yaml`, `bytetrack.yaml`, or `deepsort`) |
| `INFERENCE_WIDTH` | `640` | Frame resize width before inference |
| `FRAME_SKIP` | `2` | Process every Nth frame |
| `MIN_TRACK_FRAMES` | `2` | Frames a track must persist before being counted |
| `DEDUP_IOU` | `0.3` | IoU threshold for spatial deduplication |
| `VIDEO_CODEC` | `avc1` | Output video codec (H.264) |
| `MAX_UPLOAD_SIZE` | `500 MB` | Maximum upload file size |

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
