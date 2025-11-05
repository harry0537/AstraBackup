# Project Astra NZ - V9 Architecture Diagram

**Visual Process and Data Flow Architecture**

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROVER COMPANION PC (Ubuntu)                        │
│                         IP: 10.244.77.186 (ZeroTier)                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              HARDWARE LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ RealSense    │  │ RPLidar S3   │  │ Pixhawk 6C   │  │ SimpleRTK2B  │  │
│  │ D435i        │  │              │  │              │  │ GPS          │  │
│  │              │  │              │  │              │  │              │  │
│  │ USB Camera   │  │ /dev/ttyUSB0 │  │ /dev/ttyACM0 │  │ (GPS via     │  │
│  │ RGB/Depth/IR │  │ 1Mbps        │  │ 57600 baud   │  │  Pixhawk)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │                  │          │
│         │                  │                  │                  │          │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPONENT PROCESSES (V9)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Component 196: RealSense Vision Server V9                        │   │
│  │  PID: [dynamic]  |  Port: N/A  |  Status: RUNNING                 │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │                                                                     │   │
│  │  RESPONSIBILITIES:                                                  │   │
│  │  • Exclusive owner of RealSense camera                             │   │
│  │  • Captures RGB (640x480@15fps), Depth (424x240@15fps), IR (15fps) │   │
│  │  • Adaptive exposure control (brightness 35-75)                    │   │
│  │  • Process lock prevents duplicate instances                        │   │
│  │                                                                     │   │
│  │  OUTPUT FILES:                                                      │   │
│  │  📁 /tmp/vision_v9/                                                │   │
│  │     ├── rgb_latest.jpg        (RGB frame, JPEG)                    │   │
│  │     ├── rgb_latest.json       (metadata: frame#, timestamp, etc.)   │   │
│  │     ├── depth_latest.bin      (depth data, uint16 binary)          │   │
│  │     ├── depth_latest.jpg      (pseudo-color visualization)         │   │
│  │     ├── depth_latest.json     (metadata: dimensions, scale)        │   │
│  │     ├── ir_latest.jpg         (infrared frame, JPEG)               │   │
│  │     ├── ir_latest.json        (metadata)                           │   │
│  │     ├── status.json           (health: FPS, errors, uptime)        │   │
│  │     └── vision_server.log     (log file)                           │   │
│  │                                                                     │   │
│  │  THREADS:                                                           │   │
│  │  • Main thread: Frame capture loop (15 FPS)                        │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           │ (file reads: depth_latest.bin + metadata)       │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Component 195: Combo Proximity Bridge V9                          │   │
│  │  PID: [dynamic]  |  Port: N/A  |  Status: RUNNING                   │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │                                                                     │   │
│  │  RESPONSIBILITIES:                                                  │   │
│  │  • Reads depth data from Vision Server (no camera access)           │   │
│  │  • Connects to RPLidar S3 for 360° scanning                        │   │
│  │  • Connects to Pixhawk via MAVLink                                   │   │
│  │  • Fuses LIDAR + RealSense depth into 8 sectors (45° each)          │   │
│  │  • Sends DISTANCE_SENSOR messages to Pixhawk (10Hz)                │   │
│  │                                                                     │   │
│  │  SENSOR FUSION LOGIC:                                               │   │
│  │  • Forward sectors (0,1,7): min(LIDAR, RealSense)                  │   │
│  │  • Side/rear sectors (2-6): prefer LIDAR, fallback RealSense       │   │
│  │                                                                     │   │
│  │  OUTPUT FILES:                                                      │   │
│  │  📁 /tmp/proximity_v9.json                                          │   │
│  │     {                                                               │   │
│  │       "timestamp": ...,                                            │   │
│  │       "sectors_cm": [8 distances],                                │   │
│  │       "min_cm": ...,                                               │   │
│  │       "lidar_cm": [8 distances],                                   │   │
│  │       "realsense_cm": [8 distances],                              │   │
│  │       "messages_sent": ...,                                        │   │
│  │       "vision_server_available": true/false                        │   │
│  │     }                                                               │   │
│  │                                                                     │   │
│  │  THREADS:                                                           │   │
│  │  • LIDAR thread: Continuous scanning (~1Hz)                        │   │
│  │  • RealSense thread: Reads depth from Vision Server (~30Hz)         │   │
│  │  • Main thread: Fuses and sends to Pixhawk (10Hz)                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                           │                                                  │
│                           │ (file reads: rgb_latest.jpg + metadata)          │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Component 198: Simple Crop Monitor V9                             │   │
│  │  PID: [dynamic]  |  Port: N/A  |  Status: RUNNING                   │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │                                                                     │   │
│  │  RESPONSIBILITIES:                                                  │   │
│  │  • Reads RGB images from Vision Server (no camera access)           │   │
│  │  • Captures 1 image every 10 seconds                               │   │
│  │  • Frame deduplication (tracks frame_number)                        │   │
│  │  • Manages rolling archive (max 10 images)                          │   │
│  │  • Maintains dashboard buffer (10 slots: 1-10.jpg)                  │   │
│  │                                                                     │   │
│  │  OUTPUT FILES:                                                      │   │
│  │  📁 /tmp/crop_archive/                                              │   │
│  │     └── crop_YYYYMMDD_HHMMSS.jpg  (max 10 files)                   │   │
│  │  📁 /tmp/rover_vision/                                              │   │
│  │     ├── 1.jpg  (rolling buffer slot 1)                             │   │
│  │     ├── 2.jpg  (rolling buffer slot 2)                             │   │
│  │     ├── ...                                                         │   │
│  │     └── 10.jpg (rolling buffer slot 10)                            │   │
│  │  📁 /tmp/crop_monitor_v9.json                                       │   │
│  │     {                                                               │   │
│  │       "timestamp": ...,                                            │   │
│  │       "capture_count": ...,                                         │   │
│  │       "latest_image": "/tmp/crop_archive/crop_...jpg",             │   │
│  │       "total_archived": ...,                                        │   │
│  │       "current_slot": ...,                                          │   │
│  │       "vision_server_connected": true                               │   │
│  │     }                                                               │   │
│  │                                                                     │   │
│  │  THREADS:                                                           │   │
│  │  • Main thread: Capture loop (every 10s)                          │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Component 194: Telemetry Dashboard V9                                │   │
│  │  PID: [dynamic]  |  Port: 8081  |  Status: RUNNING                   │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │                                                                     │   │
│  │  RESPONSIBILITIES:                                                  │   │
│  │  • Flask web server (HTTP interface)                                │   │
│  │  • Reads telemetry from shared files                                │   │
│  │  • Serves HTML dashboard with real-time updates                     │   │
│  │  • Provides MJPEG video streams (RGB, Depth, IR)                  │   │
│  │  • Provides REST API for telemetry data                             │   │
│  │  • User authentication (admin/admin default)                         │   │
│  │                                                                     │   │
│  │  INPUT FILES:                                                        │   │
│  │  📁 /tmp/proximity_v9.json                                          │   │
│  │  📁 /tmp/crop_monitor_v9.json                                      │   │
│  │  📁 /tmp/vision_v9/status.json                                     │   │
│  │  📁 /tmp/vision_v9/rgb_latest.jpg (MJPEG stream)                  │   │
│  │  📁 /tmp/vision_v9/depth_latest.jpg (MJPEG stream)                 │   │
│  │  📁 /tmp/vision_v9/ir_latest.jpg (MJPEG stream)                    │   │
│  │                                                                     │   │
│  │  ENDPOINTS:                                                         │   │
│  │  • GET  /                           → Dashboard HTML               │   │
│  │  • GET  /api/telemetry               → JSON telemetry               │   │
│  │  • GET  /api/stream/rgb              → MJPEG RGB stream             │   │
│  │  • GET  /api/stream/depth            → MJPEG depth stream           │   │
│  │  • GET  /api/stream/ir               → MJPEG IR stream              │   │
│  │  • POST /login                       → Authentication               │   │
│  │  • POST /logout                      → Logout                       │   │
│  │                                                                     │   │
│  │  THREADS:                                                           │   │
│  │  • Data update thread: Reads shared files every 0.5s               │   │
│  │  • Flask main thread: Handles HTTP requests                        │   │
│  │  • MJPEG generator threads: Stream video frames                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                           ▲                                                  │
│                           │ (HTTP POST)                                       │
│                           │                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Component 197: Data Relay V9                                        │   │
│  │  PID: [dynamic]  |  Port: N/A  |  Status: RUNNING                   │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │                                                                     │   │
│  │  RESPONSIBILITIES:                                                  │   │
│  │  • Reads telemetry from Pixhawk (MAVLink)                           │   │
│  │  • Reads proximity data from /tmp/proximity_v9.json                │   │
│  │  • Reads crop images from /tmp/crop_latest.jpg                     │   │
│  │  • POSTs telemetry to Dashboard API every 2 seconds                 │   │
│  │  • POSTs images to Dashboard API every 60 seconds                  │   │
│  │                                                                     │   │
│  │  INPUT FILES:                                                        │   │
│  │  📁 /tmp/proximity_v9.json                                          │   │
│  │  📁 /tmp/crop_latest.jpg (or similar)                               │   │
│  │                                                                     │   │
│  │  NETWORK:                                                            │   │
│  │  • POST http://10.244.77.186:8081/telemetry  (every 2s)            │   │
│  │  • POST http://10.244.77.186:8081/image      (every 60s)          │   │
│  │                                                                     │   │
│  │  THREADS:                                                           │   │
│  │  • Telemetry thread: Reads MAVLink, POSTs every 2s                 │   │
│  │  • Image thread: POSTs images every 60s                            │   │
│  │  • Main thread: Status printing                                     │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
          │
          │ (MAVLink DISTANCE_SENSOR messages, 10Hz)
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PIXHAWK 6C                                      │
│                         ArduRover 4.5+ Firmware                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  RECEIVES:                                                                    │
│  • DISTANCE_SENSOR messages (8 sectors, Component 195)                       │
│    - Orientation: 0 (FRONT), 1 (F-RIGHT), 2 (RIGHT), 3 (B-RIGHT),          │
│                   4 (BACK), 5 (B-LEFT), 6 (LEFT), 7 (F-LEFT)               │
│    - Distance: 20-2500 cm                                                    │
│    - Update rate: 10Hz                                                       │
│                                                                               │
│  USES FOR:                                                                    │
│  • Obstacle avoidance (AVOID_ENABLE=7)                                      │
│  • Proximity warnings                                                        │
│  • Safe navigation                                                           │
│                                                                               │
│  STREAMS:                                                                     │
│  • GPS_RAW_INT (lat, lon, alt, fix_type)                                     │
│  • ATTITUDE (roll, pitch, yaw)                                               │
│  • SYS_STATUS (battery voltage, current, remaining)                         │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │ (MAVLink telemetry)
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROVER MANAGER V9                                     │
│                    Master Orchestration Process                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  RESPONSIBILITIES:                                                             │
│  • Ensures proper startup order (critical components first)                  │
│  • Monitors component health                                                 │
│  • Handles graceful shutdown (Ctrl+C)                                        │
│  • Prevents duplicate component starts                                       │
│                                                                               │
│  STARTUP ORDER:                                                               │
│  1. Vision Server (Component 196) - 5s delay, health check                   │
│  2. Proximity Bridge (Component 195) - 2s delay, health check               │
│  3. Crop Monitor (Component 198) - 2s delay, health check                     │
│  4. Dashboard (Component 194) - 2s delay, no health check                    │
│  5. Data Relay (Component 197) - 0s delay, no health check                   │
│                                                                               │
│  SHUTDOWN ORDER (reverse):                                                    │
│  5. Data Relay                                                                │
│  4. Dashboard                                                                 │
│  3. Crop Monitor                                                              │
│  2. Proximity Bridge                                                          │
│  1. Vision Server                                                             │
│                                                                               │
│  MONITORING:                                                                   │
│  • Checks Vision Server every 5s (critical component)                        │
│  • If Vision Server stops → shutdown all components                          │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### 1. Proximity Detection Flow

```
┌─────────────┐
│ RealSense   │
│ Camera      │
└──────┬──────┘
       │
       │ (captures depth frames)
       ▼
┌─────────────────────────────────────────┐
│ Vision Server (Component 196)          │
│ • Captures depth at 424x240@15fps      │
│ • Writes depth_latest.bin (uint16)      │
│ • Writes depth_latest.json (metadata)   │
└──────┬──────────────────────────────────┘
       │
       │ (file read: /tmp/vision_v9/depth_latest.bin)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Proximity Bridge (Component 195)                        │
│ • Reads depth frame from Vision Server                  │
│ • Processes forward sectors (0,1,7)                    │
│ • Samples depth data, calculates 5th percentile         │
│ • Updates realsense_sectors array                       │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (fuses with LIDAR data)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Sensor Fusion (Proximity Bridge)                        │
│ • Forward: min(LIDAR, RealSense)                        │
│ • Side/rear: prefer LIDAR, fallback RealSense          │
│ • Creates fused array (8 sectors)                       │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (MAVLink DISTANCE_SENSOR messages, 10Hz)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Pixhawk 6C                                              │
│ • Receives 8 DISTANCE_SENSOR messages                   │
│ • Uses for obstacle avoidance (AVOID_ENABLE=7)          │
│ • Stops/diverts if obstacle detected                    │
└──────────────────────────────────────────────────────────┘
```

### 2. Image Capture Flow

```
┌─────────────┐
│ RealSense   │
│ Camera      │
└──────┬──────┘
       │
       │ (captures RGB frames)
       ▼
┌─────────────────────────────────────────┐
│ Vision Server (Component 196)          │
│ • Captures RGB at 640x480@15fps         │
│ • Adaptive exposure control             │
│ • Writes rgb_latest.jpg (JPEG)          │
│ • Writes rgb_latest.json (metadata)     │
│   - frame_number (for deduplication)    │
│   - timestamp                           │
│   - exposure, gain, brightness          │
└──────┬──────────────────────────────────┘
       │
       │ (file read: /tmp/vision_v9/rgb_latest.jpg)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Crop Monitor (Component 198)                            │
│ • Reads image every 10 seconds                         │
│ • Checks frame_number (deduplication)                   │
│ • Validates timestamp freshness (< 2s old)             │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (saves to two locations)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Image Storage                                           │
│                                                          │
│ 📁 /tmp/crop_archive/                                   │
│    └── crop_YYYYMMDD_HHMMSS.jpg (max 10 files)         │
│                                                          │
│ 📁 /tmp/rover_vision/                                   │
│    ├── 1.jpg  (rolling buffer)                          │
│    ├── 2.jpg                                            │
│    ├── ...                                               │
│    └── 10.jpg                                            │
└──────────────────────────────────────────────────────────┘
       │
       │ (read by Dashboard for display)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Dashboard (Component 194)                              │
│ • Displays gallery of archived images                   │
│ • Shows rolling buffer (1-10)                           │
│ • MJPEG stream of latest RGB frame                      │
└──────────────────────────────────────────────────────────┘
```

### 3. Telemetry Flow

```
┌──────────────────────────────────────────────────────────┐
│ Pixhawk 6C                                              │
│ • GPS_RAW_INT (lat, lon, alt, fix)                      │
│ • ATTITUDE (roll, pitch, yaw)                          │
│ • SYS_STATUS (battery voltage, current, remaining)      │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (MAVLink messages)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Data Relay (Component 197)                              │
│ • Reads MAVLink messages                                │
│ • Reads /tmp/proximity_v9.json                          │
│ • Combines telemetry data                               │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (HTTP POST every 2s)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Dashboard API (Component 194)                           │
│ • Receives telemetry via /telemetry endpoint            │
│ • Stores in memory                                      │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (HTTP GET /api/telemetry)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Dashboard Web Interface                                 │
│ • Displays GPS coordinates                              │
│ • Shows attitude (roll, pitch, yaw)                    │
│ • Displays battery status                               │
│ • Shows proximity data (8 sectors)                     │
└──────────────────────────────────────────────────────────┘
```

---

## Process Interaction Matrix

| Component | Reads From | Writes To | Communicates With |
|-----------|-----------|-----------|-------------------|
| **Vision Server (196)** | RealSense Camera | `/tmp/vision_v9/*` | None (file-based) |
| **Proximity Bridge (195)** | `/tmp/vision_v9/depth_latest.bin`<br>RPLidar S3 | `/tmp/proximity_v9.json`<br>Pixhawk (MAVLink) | Pixhawk (MAVLink) |
| **Crop Monitor (198)** | `/tmp/vision_v9/rgb_latest.jpg` | `/tmp/crop_archive/*`<br>`/tmp/rover_vision/*`<br>`/tmp/crop_monitor_v9.json` | None (file-based) |
| **Dashboard (194)** | `/tmp/proximity_v9.json`<br>`/tmp/crop_monitor_v9.json`<br>`/tmp/vision_v9/status.json`<br>`/tmp/vision_v9/*.jpg` | HTTP responses | Clients (HTTP) |
| **Data Relay (197)** | Pixhawk (MAVLink)<br>`/tmp/proximity_v9.json`<br>`/tmp/crop_latest.jpg` | Dashboard API (HTTP) | Pixhawk (MAVLink)<br>Dashboard (HTTP) |
| **Rover Manager** | Process list (pgrep/psutil) | None | All components (process management) |

---

## File System Layout

```
/tmp/
├── vision_v9/                    # Vision Server output
│   ├── rgb_latest.jpg           # Latest RGB frame (JPEG)
│   ├── rgb_latest.json          # RGB metadata
│   ├── depth_latest.bin         # Latest depth frame (uint16 binary)
│   ├── depth_latest.jpg          # Depth pseudo-color (JPEG)
│   ├── depth_latest.json        # Depth metadata
│   ├── ir_latest.jpg            # Latest IR frame (JPEG)
│   ├── ir_latest.json           # IR metadata
│   ├── status.json              # Vision Server health status
│   ├── vision_server.log        # Log file
│   └── .lock                    # Process lock file
│
├── proximity_v9.json             # Proximity Bridge output
│   # Fused proximity data, statistics
│
├── crop_archive/                 # Crop Monitor archive
│   ├── crop_20240101_120000.jpg
│   ├── crop_20240101_120010.jpg
│   └── ... (max 10 files)
│
├── rover_vision/                 # Crop Monitor dashboard buffer
│   ├── 1.jpg                    # Rolling buffer slot 1
│   ├── 2.jpg                    # Rolling buffer slot 2
│   ├── ...
│   └── 10.jpg                   # Rolling buffer slot 10
│
├── crop_monitor_v9.json          # Crop Monitor status
│
└── astra_dashboard_users.json    # Dashboard user database
```

---

## Network Ports

| Component | Port | Protocol | Purpose |
|-----------|------|----------|---------|
| **Dashboard** | 8081 | HTTP | Web interface, API, MJPEG streams |
| **Data Relay** | N/A | HTTP (client) | POSTs to Dashboard API |

---

## Process Dependencies

```
Rover Manager
    │
    ├──► Vision Server (196) ──┐
    │                          │
    ├──► Proximity Bridge (195)├──► Depends on Vision Server
    │                          │
    ├──► Crop Monitor (198) ───┘
    │
    ├──► Dashboard (194) ───────► Depends on all (reads files)
    │
    └──► Data Relay (197) ──────► Depends on Dashboard (HTTP POST)
```

**Critical Path**: Vision Server must start before Proximity Bridge and Crop Monitor.

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Project**: Astra NZ - V9

