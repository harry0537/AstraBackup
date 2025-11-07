## Project Astra NZ — V9 Final Report

### 1. Overview
V9 delivers a standalone, modern telemetry dashboard for the rover, featuring real-time proximity visualization (LIDAR), RealSense camera streaming, GPS/attitude/battery telemetry, live logs, alerts, statistics, and a crop image gallery. The UI is implemented as a single static page (`v9/dashboard_standalone_v9.html`) for simplified deployment. A companion Flask server (`v9/telemetry_dashboard_v9.py`) provides telemetry, image streaming, and gallery APIs.

### 2. Objectives
- Provide at-a-glance system status for rover subsystems (Proximity Bridge, Data Relay, Crop Monitor)
- Visualize the proximity field with clear danger zones and sector breakdown
- Stream RealSense camera feeds (RGB/Depth/Object Detection) with availability feedback
- Display GPS, attitude, and battery metrics with contextual coloring
- Offer historical crop image browsing with a simple gallery
- Maintain lightweight, dependency-optional backend compatible with Windows and Linux

### 3. Architecture
- Frontend: Single HTML/CSS/JS file: `v9/dashboard_standalone_v9.html`
  - Components: LIDAR panel, RealSense panel, Quick Status, System Status, GPS/Telemetry, Statistics, Live Logs, Alerts, Gallery Modal
- Backend: Flask app: `v9/telemetry_dashboard_v9.py`
  - Optional deps guarded: `flask-cors`, `numpy`, `pyrealsense2`, `rplidar`
  - Auth flows (login, logout, signup) with simple file-based user store
  - Endpoints for telemetry ingest/serve, MJPEG streams, crop images listing and retrieval

### 4. Key Features
- Proximity/LIDAR visualization
  - 8 radial sectors with color-coded distance safety bands (red <1m, orange <3m, green okay)
  - High-DPI aware canvas; continuous scanning beam animation
  - Derived stats: obstacle count, min/avg distance, success rate
- RealSense camera panel
  - Stream modes: RGB, Depth, Object Detection (`/api/stream*`)
  - Placeholder overlay with automatic availability detection and fade transitions
  - FPS sparkline and status indicator
- System Status & Telemetry
  - Subsystem states: Proximity Bridge, Data Relay, Crop Monitor
  - Sensor health: RPLidar, RealSense, Pixhawk
  - GPS (lat/lon/alt, fix classification), Attitude (roll/pitch/yaw in degrees), Battery (V/A/% with coloring)
- Logs & Alerts
  - Live logs with filter chips (All/Info/Warn/Error)
  - Auto-generated alerts for common conditions; success message when nominal
- Crop Gallery
  - Modal gallery with thumbnails, lazy loading, large view, caption, and back navigation
  - No-images and error states are handled

### 5. Backend Endpoints
From `v9/telemetry_dashboard_v9.py`:
- UI/Auth
  - `/` (index)
  - `/login` (GET/POST)
  - `/logout`
  - `/signup` (GET/POST)
  - `/static/rover4.webp` (login page asset)
- Telemetry
  - `/api/telemetry` (GET current telemetry / POST updates)
  - `/telemetry` (POST alternative ingest)
  - `/api/proximity/<int:sector>/<int:distance>` (update proximity sector)
  - `/api/crop/status` (Crop monitor status)
  - Utility: may read from a shared file (`read_telemetry_file`) or simulate data (`simulate_data`)
- Camera Streams (MJPEG)
  - `/api/stream`
  - `/api/stream/depth`
  - `/api/stream/obj-detect`
- Crop Images
  - `/api/crop/latest` (serve most recent capture)
  - `/api/crop/list` (JSON list of archived images)
  - `/api/crop/archive/<path:filename>` (serve archived image)
  - `/api/crop/gallery` (simple gallery page)

### 6. Frontend Data Flow
- Periodic fetch every 2s from `/api/telemetry`
- Updates:
  - LIDAR canvas via `drawLidar(telemetryData.proximity)` and continuous animation frame redraw to maintain scanning sweep
  - Status cards via `updateStatusIndicators`
  - Live logs via `addLogEntry`/`renderLogs`
  - Alerts via `updateAlerts`
  - Quick status mirror values (mode/connection/time/heartbeat)
- Camera stream switching updates `<img id="camera-stream">` src; placeholder shown until `naturalWidth/Height` indicates a working stream

### 7. UI/UX Notes
- Neon gradient theme with strong contrast and readable typography
- Dense but structured panels with consistent spacing and borders
- Responsive behavior:
  - Single-column at <=1200px; compacted controls for narrow widths
  - Secondary panel grid enforces equal heights; scroll within panel content
- Accessibility basics: clear headings, high-contrast text, avoid critical info on color only

### 8. Setup & Run
Prerequisites (backend optional components are guarded):
- Python 3.9+
- Flask (`pip install flask`)
- Optional: `flask-cors`, `numpy`, `pyrealsense2`, `rplidar`

Environment variables (optional):
- `ASTRA_DASHBOARD_SECRET` — Flask secret key
- `ASTRA_SIGNUP_CODE` — Signup code (default `LETMEIN`)

Run (development example):
```bash
python v9/telemetry_dashboard_v9.py
```
Then open the dashboard in a browser (served root or host static file depending on your setup). For the standalone HTML, you can also open `v9/dashboard_standalone_v9.html` directly if the API host is reachable.

Windows notes:
- RealSense and RPLidar drivers/libraries are optional; the server guards imports and will run without them (streams and LIDAR endpoints will be limited accordingly).

### 9. Data Contracts (examples)
- Telemetry JSON (GET `/api/telemetry`):
```json
{
  "proximity": [2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500],
  "gps": {"lat": 0.0, "lon": 0.0, "alt": 0.0, "fix": 0},
  "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
  "battery": {"voltage": 0.0, "current": 0.0, "remaining": 0},
  "system_status": {"proximity_bridge": "Unknown", "data_relay": "Unknown", "crop_monitor": "Unknown"},
  "sensor_health": {"rplidar": "Unknown", "realsense": "Unknown", "pixhawk": "Unknown"},
  "statistics": {"uptime": 0, "messages_sent": 0, "last_update": "", "rplidar_success_rate": 0, "realsense_fps": 0}
}
```

### 10. Security & Auth
- Simple session-based auth with file-backed user store (`/tmp/astra_dashboard_users.json` by default)
- Admin bootstrap defaults to `admin/admin` if file missing; change via signup or env/config
- CORS disabled unless `flask-cors` is installed; backend prints a warning when disabled

### 11. Performance Considerations
- Canvas rendering sized to device pixel ratio; redraw throttled by requestAnimationFrame for the scanning beam, while telemetry updates arrive every 2s
- Logs capped to 200 entries; rendering limited to last 50 of the active filter
- Gallery thumbnails use `loading="lazy"` and timestamped cache-busting

### 12. Known Limitations & Future Work
- Object detection stream depends on upstream process populating frames; server exposes endpoints but does not run detectors itself
- User management is minimal and file-based; consider a persistent DB and password hashing for production
- Telemetry ingest supports JSON and simple endpoints; schema validation could be tightened
- Add WebSocket push for lower-latency updates and reduced polling

### 13. Change Summary (V9)
- Consolidated standalone HTML dashboard with refined visual design
- Improved LIDAR visualization: danger rings, sector labels, success rate, high-DPI support
- Robust camera stream placeholder/availability feedback and FPS sparkline
- Gallery modal with error/no-data handling
- Cleanup: removed debug log usage in production path and clarified CSS sections

### 14. How to Export to Word (.docx)
If you have Pandoc installed, run this command from the project root to generate a Word document:
```powershell
pandoc "v9/V9_Project_Final_Report.md" -o "v9/V9_Project_Final_Report.docx" --from gfm --toc --metadata title="Project Astra NZ — V9 Final Report"
```


