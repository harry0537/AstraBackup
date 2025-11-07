# Project Astra — Autonomous Rover Telemetry & Vision

## Mission
Real-time situational awareness for autonomous field rovers with robust sensing, live telemetry, and human-friendly monitoring.

## Problem
- Hard to trust autonomy without visibility
- Fragmented tools for sensors (LiDAR, RealSense, GPS, Pixhawk)
- Operators need one cohesive, low-latency view

## Solution
- Standalone, modern dashboard with live proximity map, camera streams, logs, alerts, and health status
- Lightweight Flask backend exposing unified telemetry and imaging APIs
- Runs with minimal dependencies; optional hardware gracefully handled

## Architecture
- Frontend: Single HTML/CSS/JS page (`v9/dashboard_standalone_v9.html`)
  - Panels: LiDAR/Proximity, RealSense, System Status, GPS & Telemetry, Statistics, Logs, Alerts, Gallery
- Backend: Flask app (`v9/telemetry_dashboard_v9.py`)
  - Auth (login/signup/logout), telemetry ingest/serve, MJPEG streams, crop gallery APIs

## Key Features
- LiDAR Proximity Radar (8 sectors, safety rings, nearest/avg distance, success rate)
- RealSense Streams (RGB / Depth / Object Detection) with seamless fallback and FPS sparkline
- GPS/Attitude/Battery with contextual coloring (good/warning/error)
- Live Logs with filtering; Auto Alerts for degraded states
- Crop Image Gallery with thumbnails, captions, and error/no-data handling

## APIs (selected)
- UI/Auth: `/`, `/login`, `/logout`, `/signup`
- Telemetry: `/api/telemetry` (GET/POST), `/telemetry` (POST), `/api/proximity/<sector>/<distance>`
- Camera: `/api/stream`, `/api/stream/depth`, `/api/stream/obj-detect`
- Gallery: `/api/crop/latest`, `/api/crop/list`, `/api/crop/archive/<filename>`, `/api/crop/status`

## Results
- Unified operator view with sub-2s periodic updates and smooth animations
- Graceful operation even when optional hardware or services are unavailable
- Simple deployment: open the HTML or run the Flask app

## Tech Stack
- Frontend: Vanilla HTML/CSS/JS (no frameworks)
- Backend: Python + Flask (optional: flask-cors, numpy, pyrealsense2, rplidar)

## Safety & Reliability
- Visual danger zones (<1m red, <3m orange)
- Health/status cards for critical services and sensors
- Logs and alerts to surface real-time issues

## What’s Next
- WebSocket push for lower latency
- Hardened auth and persistent user management
- Onboard object detection pipeline integration

## How to Run
```bash
python v9/telemetry_dashboard_v9.py  # starts the Flask server
# or open v9/dashboard_standalone_v9.html directly if APIs are reachable
```

## Export Poster
If Pandoc is installed, you can export this poster:
```powershell
# DOCX
pandoc "v9/Project_Astra_Poster.md" -o "v9/Project_Astra_Poster.docx" --from gfm --metadata title="Project Astra — Poster"

# PDF (requires LaTeX)
pandoc "v9/Project_Astra_Poster.md" -o "v9/Project_Astra_Poster.pdf" --from gfm -V geometry:margin=1in --metadata title="Project Astra — Poster"

# PPTX
pandoc "v9/Project_Astra_Poster.md" -o "v9/Project_Astra_Poster.pptx" --from gfm --metadata title="Project Astra — Poster"
```

---
Developed by Harinder Singh — Project Astra NZ

