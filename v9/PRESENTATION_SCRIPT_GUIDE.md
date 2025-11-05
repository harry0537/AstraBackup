# Project Astra NZ - V9 Script Overview
**Quick Reference Guide for Presentations**

---

## Overview

V9 uses a **single-owner architecture** to eliminate hardware conflicts. Each script has a specific responsibility and communicates via shared files.

---

## Scripts Summary

### 1. **Rover Manager** (`rover_manager_v9.py`)
**What it does:** Master orchestrator that starts and monitors all components.

**Key responsibilities:**
- Starts all components in the correct order (Vision Server first, then others)
- Monitors component health
- Handles graceful shutdown (Ctrl+C stops everything cleanly)
- Prevents duplicate instances

**Why it's needed:** Ensures components start in the right order and monitors critical components.

**When you'd mention it:** "Our system uses a manager script that ensures all components start in the correct sequence and monitors their health."

---

### 2. **Vision Server** (`realsense_vision_server_v9.py`)
**What it does:** Exclusive owner of the RealSense camera. Captures RGB, depth, and IR frames.

**Key responsibilities:**
- Owns the RealSense D435i camera (no other component can access it)
- Captures RGB (640x480@15fps), Depth (424x240@15fps), IR (15fps)
- Adaptive exposure control (adjusts brightness automatically)
- Writes frames to shared files: `/tmp/vision_v9/rgb_latest.jpg`, `depth_latest.bin`, `ir_latest.jpg`
- Writes metadata (frame numbers, timestamps) for deduplication

**Why it's needed:** Prevents camera conflicts. Other components read from files instead of accessing the camera directly.

**When you'd mention it:** "We solved camera conflicts by having one dedicated Vision Server that owns the camera and writes frames to shared files. Other components read these files instead of accessing the camera directly."

**Output files:**
- `/tmp/vision_v9/rgb_latest.jpg` + `rgb_latest.json`
- `/tmp/vision_v9/depth_latest.bin` + `depth_latest.json`
- `/tmp/vision_v9/ir_latest.jpg` + `ir_latest.json`
- `/tmp/vision_v9/status.json` (health status)

---

### 3. **Proximity Bridge** (`combo_proximity_bridge_v9.py`)
**What it does:** Fuses LIDAR and RealSense depth data, sends proximity information to Pixhawk for obstacle avoidance.

**Key responsibilities:**
- Reads depth data from Vision Server (no camera access)
- Connects to RPLidar S3 for 360° scanning
- Connects to Pixhawk via MAVLink
- Fuses both sensors: RealSense for forward (most critical), LIDAR for sides/rear
- Divides data into 8 sectors (45° each): FRONT, F-RIGHT, RIGHT, B-RIGHT, BACK, B-LEFT, LEFT, F-LEFT
- Sends `DISTANCE_SENSOR` messages to Pixhawk at 10Hz (8 messages per update)
- Writes status to `/tmp/proximity_v9.json`

**Why it's needed:** Provides obstacle detection data to Pixhawk's obstacle avoidance system.

**When you'd mention it:** "Our Proximity Bridge fuses LIDAR and depth camera data into 8 sectors and sends it to Pixhawk at 10Hz. This enables real-time obstacle avoidance."

**Sensor fusion logic:**
- Forward sectors (0, 1, 7): Uses minimum of RealSense and LIDAR (most reliable)
- Side/rear sectors (2-6): Prefers LIDAR when available, falls back to RealSense

**Output files:**
- `/tmp/proximity_v9.json` (fused proximity data, statistics)

**MAVLink messages:**
- Sends 8 `DISTANCE_SENSOR` messages per update (one per sector)
- Orientation values: 0=FRONT, 1=45°, 2=90°, 3=135°, 4=180°, 5=225°, 6=270°, 7=315°

---

### 4. **Crop Monitor** (`simple_crop_monitor_v9.py`)
**What it does:** Captures crop images from Vision Server for analysis and documentation.

**Key responsibilities:**
- Reads RGB images from Vision Server (no camera access)
- Captures 1 image every 10 seconds
- Frame deduplication (tracks frame numbers to avoid processing same frame twice)
- Manages rolling archive: keeps maximum 10 archived images (`/tmp/crop_archive/`)
- Maintains dashboard buffer: 10 rolling slots (`/tmp/rover_vision/1-10.jpg`)
- Writes status to `/tmp/crop_monitor_v9.json`

**Why it's needed:** Provides crop monitoring data for analysis and documentation.

**When you'd mention it:** "Our Crop Monitor captures images every 10 seconds and maintains a rolling archive. It uses frame deduplication to avoid processing duplicate frames."

**Output files:**
- `/tmp/crop_archive/crop_YYYYMMDD_HHMMSS.jpg` (max 10 files)
- `/tmp/rover_vision/1.jpg` through `10.jpg` (rolling dashboard buffer)
- `/tmp/crop_monitor_v9.json` (status)

---

### 5. **Telemetry Dashboard** (`telemetry_dashboard_v9.py`)
**What it does:** Flask web server providing real-time monitoring interface.

**Key responsibilities:**
- Web dashboard on port 8081
- Reads telemetry from shared files (`/tmp/proximity_v9.json`, `/tmp/crop_monitor_v9.json`, etc.)
- Displays LIDAR radar, camera streams, system status, statistics
- Provides MJPEG video streams: RGB, Depth (pseudo-color), IR
- REST API endpoints: `/api/telemetry`, `/api/stream/rgb`, `/api/stream/depth`, `/api/stream/ir`
- User authentication (admin/admin default)

**Why it's needed:** Provides real-time monitoring and control interface.

**When you'd mention it:** "Our web dashboard displays real-time telemetry, LIDAR radar visualization, and live camera streams. It reads from shared files, so it doesn't interfere with other components."

**Endpoints:**
- `GET /` - Dashboard HTML
- `GET /api/telemetry` - JSON telemetry data
- `GET /api/stream/rgb` - MJPEG RGB stream
- `GET /api/stream/depth` - MJPEG depth stream (pseudo-color)
- `GET /api/stream/ir` - MJPEG IR stream

**Input files (reads):**
- `/tmp/proximity_v9.json`
- `/tmp/crop_monitor_v9.json`
- `/tmp/vision_v9/status.json`
- `/tmp/vision_v9/rgb_latest.jpg` (for MJPEG stream)
- `/tmp/vision_v9/depth_latest.jpg` (for MJPEG stream)
- `/tmp/vision_v9/ir_latest.jpg` (for MJPEG stream)

---

### 6. **Data Relay** (`data_relay_v9.py`)
**What it does:** Relays telemetry and images to remote dashboard via HTTP.

**Key responsibilities:**
- Reads telemetry from Pixhawk (MAVLink: GPS, attitude, battery)
- Reads proximity data from `/tmp/proximity_v9.json`
- Reads crop images from `/tmp/crop_latest.jpg`
- POSTs telemetry to Dashboard API every 2 seconds
- POSTs images to Dashboard API every 60 seconds
- Compresses images before sending (resizes to max 1024x768, JPEG quality 75)

**Why it's needed:** Enables remote monitoring by relaying data to a remote dashboard.

**When you'd mention it:** "Our Data Relay component reads telemetry from Pixhawk and proximity data from shared files, then sends it to a remote dashboard for monitoring."

**Network:**
- POSTs to `http://10.244.77.186:8081/telemetry` (every 2s)
- POSTs to `http://10.244.77.186:8081/image` (every 60s)

**Input files (reads):**
- `/tmp/proximity_v9.json`
- `/tmp/crop_latest.jpg` (or similar)

---

## Communication Flow

### File-Based Communication (IPC)
```
Vision Server → [files] → Proximity Bridge (reads depth)
Vision Server → [files] → Crop Monitor (reads RGB)
Vision Server → [files] → Dashboard (reads all streams)
Proximity Bridge → [files] → Dashboard (reads proximity data)
Proximity Bridge → [files] → Data Relay (reads proximity data)
Crop Monitor → [files] → Dashboard (reads crop images)
```

### MAVLink Communication
```
Proximity Bridge → [MAVLink] → Pixhawk (DISTANCE_SENSOR messages)
Data Relay ↔ [MAVLink] ↔ Pixhawk (GPS, attitude, battery)
```

### HTTP Communication
```
Dashboard → [HTTP] → Remote clients (web interface, MJPEG streams)
Data Relay → [HTTP POST] → Dashboard API (telemetry, images)
```

---

## Startup Order (Critical)

1. **Vision Server** (must start first - owns camera)
2. **Proximity Bridge** (waits for Vision Server)
3. **Crop Monitor** (waits for Vision Server)
4. **Dashboard** (non-critical, can start anytime)
5. **Data Relay** (non-critical, can start anytime)

**Why this order matters:** Vision Server must start first because other components depend on its output files.

---

## Key Architecture Benefits

### 1. No Camera Conflicts
- **Problem solved:** Multiple components trying to access the same camera
- **Solution:** Vision Server is the exclusive owner, others read from files

### 2. Frame Deduplication
- **Problem solved:** Processing the same frame multiple times
- **Solution:** Metadata includes frame numbers, components track last processed frame

### 3. Atomic File Writes
- **Problem solved:** Reading corrupted files during write
- **Solution:** Write to `.tmp` file, then `os.replace()` (atomic operation)

### 4. Process Locking
- **Problem solved:** Multiple instances of Vision Server running
- **Solution:** Process lock file prevents duplicates

---

## Common Questions & Answers

### Q: "Why not just have each component access the camera directly?"
**A:** "We tried that in V8 and had constant camera conflicts. In V9, we use a single-owner pattern where Vision Server exclusively owns the camera and writes frames to shared files. This eliminates conflicts entirely."

### Q: "How do you ensure data consistency?"
**A:** "We use atomic file writes (write to `.tmp` then rename), frame deduplication via metadata, and proper locking mechanisms. Each component tracks the last processed frame number to avoid duplicates."

### Q: "What happens if Vision Server crashes?"
**A:** "The Rover Manager monitors Vision Server (it's marked as critical). If it crashes, the manager shuts down all components gracefully. Other components can detect Vision Server unavailability by checking status file age."

### Q: "How does obstacle avoidance work?"
**A:** "Proximity Bridge fuses LIDAR and RealSense depth data into 8 sectors, then sends DISTANCE_SENSOR messages to Pixhawk at 10Hz. Pixhawk uses this data with parameters AVOID_ENABLE=7 and AVOID_MARGIN=30cm to stop or avoid obstacles."

### Q: "What's the update rate?"
**A:** "Vision Server captures at 15 FPS, Proximity Bridge sends to Pixhawk at 10Hz, Dashboard updates telemetry display at 2Hz, and Data Relay sends to remote dashboard every 2 seconds for telemetry and 60 seconds for images."

### Q: "How do you handle errors?"
**A:** "Each component has error handling with retry logic, graceful degradation (e.g., LIDAR-only mode if Vision Server unavailable), and status files that other components can check. The manager monitors critical components and shuts down on failure."

### Q: "Why 8 sectors for proximity detection?"
**A:** "8 sectors provide 45° resolution, which is sufficient for obstacle avoidance while keeping message count manageable. We send 8 DISTANCE_SENSOR messages per update (one per sector)."

### Q: "How does sensor fusion work?"
**A:** "For forward sectors (most critical), we use the minimum of RealSense and LIDAR for maximum reliability. For side/rear sectors, we prefer LIDAR when available since it provides 360° coverage."

### Q: "What's the range of obstacle detection?"
**A:** "Minimum distance: 20cm, Maximum distance: 25 meters. This covers typical obstacle avoidance needs for a rover."

### Q: "How do components know if another component is running?"
**A:** "Components check status files (e.g., `/tmp/vision_v9/status.json`) with timestamps. If a status file is older than 5 seconds, the component is considered unavailable."

---

## File Locations Reference

### Vision Server Output
- `/tmp/vision_v9/rgb_latest.jpg` + `.json`
- `/tmp/vision_v9/depth_latest.bin` + `.json` + `.jpg`
- `/tmp/vision_v9/ir_latest.jpg` + `.json`
- `/tmp/vision_v9/status.json`

### Proximity Bridge Output
- `/tmp/proximity_v9.json`

### Crop Monitor Output
- `/tmp/crop_archive/crop_*.jpg` (max 10)
- `/tmp/rover_vision/1-10.jpg` (rolling buffer)
- `/tmp/crop_monitor_v9.json`

---

## Quick Facts

- **Total components:** 5 (Vision Server, Proximity Bridge, Crop Monitor, Dashboard, Data Relay)
- **Update rates:** Vision Server 15 FPS, Proximity Bridge 10Hz, Dashboard 2Hz
- **Sectors:** 8 (45° each)
- **Distance range:** 20cm - 25m
- **Camera resolution:** RGB 640x480, Depth 424x240
- **Network ports:** Dashboard 8081
- **File-based IPC:** All components communicate via `/tmp/` files
- **MAVLink:** Proximity Bridge and Data Relay communicate with Pixhawk

---

**Document Version:** 1.0  
**Created for:** Project Astra NZ - V9 Presentation  
**Last Updated:** 2024

