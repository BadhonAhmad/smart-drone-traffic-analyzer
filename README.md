# Smart Drone Traffic Analyzer

## Overview

Smart Drone Traffic Analyzer is a full-stack web application that processes drone surveillance video to detect, track, and count vehicles in real time. It uses YOLOv8 object detection with ByteTrack multi-object tracking to identify cars, trucks, buses, and motorcycles, then produces an annotated output video and a downloadable Excel report. The frontend streams live progress via WebSocket so users can monitor analysis as it happens.

## Architecture

```
  Browser (Next.js 14)
       |
       |  REST + WebSocket (proxied via Next.js rewrites)
       v
  FastAPI Backend
       |
       +-- BackgroundTask -> run_pipeline()
       |        |
       |        +-- YOLOv8n (object detection)
       |        +-- ByteTrack (multi-object tracking)
       |        +-- Virtual Line Counter (unique vehicle counting)
       |        +-- OpenCV (frame annotation + video export)
       |
       +-- report.py -> Excel (.xlsx) generation
```

## Tech Stack

| Layer       | Technology          | Reason                                              |
|-------------|---------------------|------------------------------------------------------|
| Backend     | Python + FastAPI    | Async-native, auto OpenAPI docs, fast development    |
| CV          | Ultralytics YOLOv8n | Lightweight detection with strong COCO pre-training  |
| Tracking    | ByteTrack           | No separate re-ID model needed, fast, handles occlusions |
| Video I/O   | OpenCV              | Frame-level read/write, drawing, resize              |
| Reports     | openpyxl            | Styled multi-sheet Excel generation                  |
| Frontend    | Next.js 14 (App Router) | Server-proxyable rewrites, React components       |
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

Or use the launcher script:

```bash
chmod +x run.sh
./run.sh
```

## How It Works

### CV Pipeline

1. **Upload** — The user drops an `.mp4` file. The backend validates the extension and MP4 magic bytes (`ftyp` at offset 4), saves the file, creates a job, and kicks off a background task.

2. **Detection** — Every 2nd frame is resized to 640 px width and passed through YOLOv8n with ByteTrack tracking (`classes=[2,3,5,7]` filtering to car, motorcycle, bus, truck).

3. **Counting** — A virtual red line at 50% frame height acts as a counting trigger. A vehicle is counted the first time its bounding-box center crosses this line.

4. **Annotation** — Every processed frame gets colored bounding boxes (blue=car, red=truck, yellow=bus, green=motorcycle), ID labels, and a HUD overlay showing the running count.

5. **Output** — The annotated video is written via `cv2.VideoWriter` at original resolution and FPS. An Excel report with three sheets is generated automatically.

### Tracking and Counting Logic

- **`seen_track_ids` set** — Once a track ID is added, it is never counted again, preventing double-counts from U-turns or tracker jitter.
- **Virtual line crossing** — The previous and current center-Y of each track are compared against the 50% height line to detect a crossing event.
- **30-frame fallback** — Vehicles tracked for 30+ processed frames without crossing the line are force-counted, catching stationary or edge-visible vehicles.
- **Class voting** — The most frequently detected class per track ID is used as the final classification, reducing mislabels from single-frame errors.
- **ByteTrack** — Two-stage association (high then low confidence) handles occlusions without a heavyweight re-ID model.

### Edge Cases Handled

- **Vehicle stops mid-scene** — The 30-frame fallback ensures stationary vehicles are still counted.
- **Vehicle passes behind occlusion** — ByteTrack's low-confidence association stage re-links tracks after brief disappearances.
- **Vehicle visible but never crosses line** — The fallback counter catches these after 30 tracked frames.
- **Invalid file upload** — Extension, content-type, and MP4 magic-byte validation all reject non-video files with a clear error message.
- **WebSocket disconnect mid-processing** — The frontend auto-reconnects up to 3 times with a 3-second delay, showing a "Connection lost. Retrying..." warning.
- **File too large** — Frontend rejects files over 500 MB before upload.

## API Reference

| Method | Endpoint                  | Description                              |
|--------|---------------------------|------------------------------------------|
| POST   | `/api/upload`             | Upload an .mp4 video for analysis        |
| GET    | `/api/job/{job_id}`       | Get current job status and progress      |
| WS     | `/ws/progress/{job_id}`   | Stream real-time progress updates        |
| GET    | `/api/result/{job_id}`    | Get final analysis result JSON           |
| GET    | `/api/report/{job_id}`    | Download Excel report (.xlsx)            |
| GET    | `/api/video/{job_id}`     | Download annotated output video (.mp4)   |

## Engineering Assumptions

- Drone footage is top-down or near-top-down视角, making a horizontal counting line effective.
- Input framerate is approximately 25-30 fps; frame skipping to 15 fps effective retains sufficient temporal resolution.
- Vehicles move through the frame (entering and exiting); purely stationary scenes are not the target use case.
- YOLOv8n (nano) provides sufficient accuracy for traffic counting; larger models can be swapped in for higher precision.
- MP4 is the only supported container format to keep validation simple.
- The backend is single-instance; job state is kept in memory (not persisted across restarts).
- The virtual counting line at 50% height works for typical drone altitudes where vehicles traverse most of the frame vertically.

## Report Format

The generated Excel file contains three sheets:

1. **Summary** — Job ID, total unique vehicles, processing duration, per-type counts, report timestamp. Bold labels with accent-colored header row.

2. **Vehicle Breakdown** — Class, count, and percentage of total for each vehicle type. Centered values with styled header.

3. **Detection Log** — One row per counting event: track ID, class, confidence, frame number, timestamp, and bounding box coordinates. Alternating row fills for readability, auto-fitted column widths.

## Demo

_Coming soon_
