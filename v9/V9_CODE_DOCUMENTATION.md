# Project Astra NZ - V9 Code Documentation

**Complete Step-by-Step Guide to All V9 Scripts and Processes**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Script Documentation](#script-documentation)
   - [Rover Manager](#1-rover-manager-v9)
   - [Vision Server](#2-realsense-vision-server-v9)
   - [Proximity Bridge](#3-combo-proximity-bridge-v9)
   - [Crop Monitor](#4-simple-crop-monitor-v9)
   - [Telemetry Dashboard](#5-telemetry-dashboard-v9)
   - [Data Relay](#6-data-relay-v9)
   - [Parameter Application Tool](#7-parameter-application-tool)
4. [Process Communication](#process-communication)
5. [Data Flow](#data-flow)

---

## Overview

**V9 Architecture Philosophy**: Single-owner pattern for hardware resources to eliminate conflicts.

- **Vision Server (Component 196)**: Exclusive owner of RealSense camera
- **Proximity Bridge (Component 195)**: Reads depth from Vision Server, owns LIDAR
- **Crop Monitor (Component 198)**: Reads RGB from Vision Server
- **Dashboard (Component 194)**: Web interface, reads telemetry from shared files
- **Data Relay (Component 197)**: Relays telemetry to remote dashboard

**Key Improvement**: No camera conflicts - Vision Server owns camera, others read files.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ROVER COMPANION PC (Ubuntu)                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    HARDWARE INTERFACES                           │
├─────────────────────────────────────────────────────────────────┤
│  RealSense D435i  │  RPLidar S3  │  Pixhawk 6C  │  SimpleRTK2B  │
│   (USB Camera)    │  (/dev/ttyUSB)│  (/dev/ttyACM)│   (GPS)      │
└─────────────────────────────────────────────────────────────────┘
         │                │              │              │
         │                │              │              │
         ▼                ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    COMPONENT PROCESSES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Component 196: RealSense Vision Server V9              │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  • Exclusive owner of RealSense camera                   │  │
│  │  • Captures RGB, Depth, IR frames at 15 FPS              │  │
│  │  • Writes to /tmp/vision_v9/:                           │  │
│  │    - rgb_latest.jpg + rgb_latest.json                   │  │
│  │    - depth_latest.bin + depth_latest.json               │  │
│  │    - ir_latest.jpg + ir_latest.json                    │  │
│  │    - status.json (health status)                        │  │
│  │  • Process lock prevents duplicates                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           │ (file reads)                        │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Component 195: Combo Proximity Bridge V9                │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  • Reads depth_latest.bin from Vision Server            │  │
│  │  • Connects to RPLidar S3 (/dev/ttyUSB0)                │  │
│  │  • Connects to Pixhawk via MAVLink (/dev/ttyACM0)       │  │
│  │  • Fuses LIDAR + RealSense depth into 8 sectors        │  │
│  │  • Sends DISTANCE_SENSOR messages to Pixhawk (10Hz)     │  │
│  │  • Writes /tmp/proximity_v9.json                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           │ (file reads)                        │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Component 198: Simple Crop Monitor V9                 │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  • Reads rgb_latest.jpg from Vision Server               │  │
│  │  • Captures 1 image every 10 seconds                    │  │
│  │  • Archives to /tmp/crop_archive/ (max 10 images)       │  │
│  │  • Writes rolling buffer to /tmp/rover_vision/ (1-10)   │  │
│  │  • Writes /tmp/crop_monitor_v9.json (status)            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Component 194: Telemetry Dashboard V9                  │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  • Flask web server (port 8081)                          │  │
│  │  • Reads /tmp/proximity_v9.json                         │  │
│  │  • Reads /tmp/crop_monitor_v9.json                      │  │
│  │  • Reads /tmp/vision_v9/status.json                     │  │
│  │  • Serves MJPEG streams:                                │  │
│  │    - /api/stream/rgb (from Vision Server)               │  │
│  │    - /api/stream/depth (pseudo-color)                   │  │
│  │    - /api/stream/ir                                     │  │
│  │  • Provides /api/telemetry endpoint                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                           │ (HTTP)                              │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Component 197: Data Relay V9                            │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  • Reads telemetry from Pixhawk (MAVLink)                │  │
│  │  • Reads /tmp/proximity_v9.json                         │  │
│  │  • Reads /tmp/crop_latest.jpg                           │  │
│  │  • POSTs telemetry to Dashboard API every 2 seconds    │  │
│  │  • POSTs images to Dashboard API every 60 seconds       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
         │
         │ (MAVLink)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PIXHAWK 6C                                    │
│  • Receives DISTANCE_SENSOR messages (8 sectors)              │
│  • Uses for obstacle avoidance (AVOID_ENABLE=7)                │
│  • Streams telemetry back via MAVLink                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ROVER MANAGER V9                              │
│  • Orchestrates startup/shutdown of all components              │
│  • Ensures proper startup order                                 │
│  • Monitors critical components                                 │
│  • Clean shutdown on Ctrl+C                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Script Documentation

### 1. Rover Manager V9

**File**: `rover_manager_v9.py`  
**Purpose**: Orchestrates startup, shutdown, and monitoring of all V9 components.

#### Step-by-Step Execution:

1. **Initialization** (`__init__`):
   - Detects Python executable (venv if available, system otherwise)
   - Initializes `processes` dictionary to track component PIDs
   - Sets `running = True` flag

2. **Directory Setup** (`setup_directories`):
   - Creates `/tmp/vision_v9` (Vision Server output)
   - Creates `/tmp/crop_archive` (Crop Monitor archive)
   - Creates `/tmp/rover_vision` (Dashboard rolling buffer)

3. **Component Start** (`start_component`):
   - Checks if component is already running (cross-platform):
     - Unix: Uses `pgrep -f script_name`
     - Windows: Uses `psutil` if available
   - Starts process with `subprocess.Popen`
   - Waits 2 seconds, checks if process is still alive
   - Applies `startup_delay` (Vision Server: 5s, others: 2s)
   - Runs `health_check` function (checks for status files)
   - Returns process object or None

4. **Startup Sequence** (`run`):
   - Calls `setup_directories()`
   - Checks if any V9 components are already running
   - Starts components in CRITICAL order:
     1. **Vision Server (196)** - Must start first (5s delay)
     2. **Proximity Bridge (195)** - Waits for Vision Server (2s delay)
     3. **Crop Monitor (198)** - Waits for Vision Server (2s delay)
     4. **Dashboard (194)** - Non-critical (2s delay)
     5. **Data Relay (197)** - Non-critical (0s delay)
   - If critical component fails, stops all and exits
   - Prints startup summary with access URLs

5. **Monitoring Loop**:
   - Sleeps for 5 seconds
   - Checks if Vision Server (critical) is still running
   - If Vision Server stops, exits and shuts down all

6. **Shutdown** (`stop_all`):
   - Stops components in reverse order
   - Sends SIGTERM to each process
   - Waits 5 seconds, then sends SIGKILL if needed
   - Cleans up any remaining processes with `pkill`

#### Key Functions:
- `get_python_executable()`: Returns venv Python or system Python
- `start_component(component)`: Starts single component with health checks
- `stop_all()`: Graceful shutdown of all components
- `run()`: Main execution loop

---

### 2. RealSense Vision Server V9

**File**: `realsense_vision_server_v9.py`  
**Component ID**: 196  
**Purpose**: Exclusive owner of RealSense camera, provides RGB/Depth/IR streams via shared files.

#### Step-by-Step Execution:

1. **Process Lock** (`ProcessLock`):
   - **Unix**: Uses `fcntl.flock()` for exclusive lock on `/tmp/vision_v9/.lock`
   - **Windows**: Uses file-based locking with `psutil` to check if PID is running
   - Prevents multiple instances from running simultaneously
   - Writes PID to lock file

2. **Initialization** (`VisionServer.__init__`):
   - Creates `/tmp/vision_v9` directory
   - Opens log file (`vision_server.log`)
   - Initializes statistics counters (rgb_frames, depth_frames, ir_frames, errors)
   - Sets exposure control parameters (exposure_us, gain_value)
   - Frame number counter starts at 0

3. **Camera Connection** (`connect_camera`):
   - Creates RealSense pipeline and config
   - Enables streams:
     - RGB: 640x480 @ 15 FPS (BGR8 format)
     - Depth: 424x240 @ 15 FPS (Z16 format, uint16 millimeters)
     - IR: 640x480 @ 15 FPS (Y8 format, mono)
   - Starts pipeline
   - Calls `configure_camera()` to set manual exposure/gain
   - Waits 2 seconds for stabilization
   - Captures test frames to verify connection
   - Returns True on success

4. **Camera Configuration** (`configure_camera`):
   - Finds RGB sensor in device
   - Disables auto-exposure
   - Sets manual exposure (6000µs default)
   - Sets manual gain (32.0 default)
   - Disables auto-exposure priority
   - Enables backlight compensation

5. **Adaptive Exposure Control** (`adjust_rgb_exposure`):
   - Calculates mean brightness from grayscale image
   - If brightness > 75: Reduces exposure by 500µs, reduces gain by 2
   - If brightness < 35: Increases exposure by 500µs, increases gain by 2
   - Limits: exposure 500-20000µs, gain 8-64
   - Updates every 0.4 seconds max

6. **Frame Writing** (`write_rgb_frame`, `write_depth_frame`, `write_ir_frame`):
   - **RGB Frame**:
     - Increments frame_number
     - Calculates brightness for exposure control
     - Writes JPEG to `rgb_latest.jpg.tmp`, then `os.replace()` to `rgb_latest.jpg` (atomic)
     - Writes metadata JSON: frame_number, timestamp, dimensions, FPS, exposure, gain, brightness
   - **Depth Frame**:
     - Converts depth frame to numpy array (uint16, millimeters)
     - Writes binary data to `depth_latest.bin` (atomic write)
     - Also creates pseudo-color JPEG: normalizes 0-5000mm to 0-255, inverts, applies colormap
     - Writes metadata JSON: frame_number, timestamp, dimensions, depth_scale, data_type
   - **IR Frame**:
     - Converts IR frame to numpy array (Y8 mono)
     - Writes JPEG to `ir_latest.jpg` (atomic)
     - Writes metadata JSON: frame_number, timestamp, dimensions

7. **Status Update** (`update_status`):
   - Calculates actual FPS (frames / uptime)
   - Writes JSON to `status.json`:
     - Component ID, name, status: "RUNNING"
     - Uptime, frames processed, actual/target FPS
     - Error count, last error message
     - Timestamp, PID
   - Updates every 1 second

8. **Main Capture Loop** (`capture_loop`):
   - Continuously waits for frames with 1s timeout
   - Extracts color, depth, and infrared frames
   - Handles IR frame extraction (may need index parameter)
   - Calls `write_rgb_frame()`, `write_depth_frame()`, `write_ir_frame()`
   - Calls `update_status()` every 1 second
   - On consecutive errors > 50: Attempts camera restart
   - On camera restart failure: Exits

9. **Shutdown** (`shutdown`):
   - Sets `running = False`
   - Stops pipeline
   - Writes final status: `status: "STOPPED"`
   - Closes log file
   - Releases process lock

#### Key Functions:
- `ProcessLock.acquire()`: Acquires exclusive lock (prevents duplicates)
- `connect_camera()`: Initializes RealSense camera with streams
- `write_rgb_frame()`: Atomic write of RGB JPEG + metadata
- `write_depth_frame()`: Atomic write of depth binary + pseudo-color JPEG + metadata
- `write_ir_frame()`: Atomic write of IR JPEG + metadata
- `update_status()`: Writes health status JSON
- `capture_loop()`: Main frame capture and writing loop

#### Output Files:
- `/tmp/vision_v9/rgb_latest.jpg` + `rgb_latest.json`
- `/tmp/vision_v9/depth_latest.bin` + `depth_latest.json` + `depth_latest.jpg`
- `/tmp/vision_v9/ir_latest.jpg` + `ir_latest.json`
- `/tmp/vision_v9/status.json`
- `/tmp/vision_v9/vision_server.log`

---

### 3. Combo Proximity Bridge V9

**File**: `combo_proximity_bridge_v9.py`  
**Component ID**: 195  
**Purpose**: Fuses LIDAR and RealSense depth data, sends proximity messages to Pixhawk.

#### Step-by-Step Execution:

1. **Initialization** (`ComboProximityBridge.__init__`):
   - Loads hardware config from `rover_config_v9.json` (LIDAR port, Pixhawk port)
   - Initializes proximity configuration:
     - min_distance_cm: 20
     - max_distance_cm: 2500
     - quality_threshold: 10
     - num_sectors: 8
   - Creates thread-safe storage: `lidar_sectors`, `realsense_sectors` (8 elements each)
   - Initializes statistics counters
   - Sets up stderr redirection for LIDAR warnings suppression
   - Tracks Vision Server frame numbers (for deduplication)

2. **Vision Server Check** (`check_vision_server`):
   - Reads `/tmp/vision_v9/status.json`
   - Validates timestamp is < 5 seconds old
   - Checks status == "RUNNING"
   - Returns True if Vision Server is available

3. **Depth Data Reading** (`read_depth_from_vision_server`):
   - Reads `/tmp/vision_v9/depth_latest.json` (metadata)
   - Validates metadata has `timestamp` and `frame_number`
   - Checks data freshness (< 1 second old)
   - Checks frame_number != last processed (deduplication)
   - Reads `/tmp/vision_v9/depth_latest.bin` (binary uint16 array)
   - Validates array size matches width × height
   - Reshapes to 2D array (height, width)
   - Updates `last_depth_frame_number`
   - Returns (depth_frame, metadata, success)

4. **LIDAR Connection** (`connect_lidar`):
   - Attempts connection to `/dev/ttyUSB0` (or config port)
   - Uses `RPLidar` library, baudrate 1000000
   - Gets device info and health status
   - Retries up to 5 times on failure
   - Returns True on success

5. **Pixhawk Connection** (`connect_pixhawk`):
   - Tries config port first, then `/dev/ttyACM0-3`
   - Creates MAVLink connection (baud 57600, component ID 195)
   - Waits for heartbeat (5s timeout)
   - Returns True on success

6. **LIDAR Thread** (`lidar_thread`):
   - Redirects stderr to suppress buffer warnings
   - Continuously:
     - Starts LIDAR motor
     - Waits 0.5s for stabilization
     - Collects scan data using `iter_scans(max_buf_meas=500)`
     - Filters points by quality > threshold
     - Divides into 8 sectors (45° each, starting at -22.5°)
     - Finds minimum distance per sector
     - Updates `lidar_sectors` (thread-safe)
     - Stops motor
     - Sleeps 0.5s
   - On errors: Attempts reconnection after 10 errors
   - Restores stderr on exit

7. **RealSense Thread** (`realsense_thread_v9`):
   - Continuously calls `read_depth_from_vision_server()`
   - On success:
     - Processes depth frame (same logic as V8)
     - Divides frame into 3 forward regions (center, right, left)
     - Samples every 10 pixels in each region
     - Filters depths 0.2-25.0m
     - Calculates 5th percentile (closest valid depth)
     - Updates sectors 0, 1, 7 (forward arc) with RealSense data
   - On failure: Tracks consecutive failures, warns after 10
   - Sleeps 0.03s (~30Hz)

8. **Sensor Fusion** (`fuse_and_send`):
   - Reads `lidar_sectors` and `realsense_sectors` (thread-safe)
   - Creates `fused` array (8 sectors)
   - For forward sectors (0, 1, 7): Uses minimum of RealSense and LIDAR
   - For side/rear sectors (2-6): Prefers LIDAR if available, else RealSense
   - Sends 8 `DISTANCE_SENSOR` messages to Pixhawk:
     - One message per sector (orientation 0-7)
     - Timestamp, min/max distance, current distance (cm)
     - Type 0, ID = sector index, orientation = sector index
   - Increments `messages_sent` counter
   - Writes `/tmp/proximity_v9.json` (atomic):
     - Timestamp, sectors_cm, min_cm
     - lidar_cm, realsense_cm (separate arrays)
     - messages_sent, errors, vision_server_available

9. **Main Loop** (`run`):
   - Waits up to 30 seconds for Vision Server
   - Connects to Pixhawk (required)
   - Connects to LIDAR (best effort)
   - Starts LIDAR thread (if LIDAR available)
   - Starts RealSense thread (if Vision Server available)
   - Main loop:
     - Calls `fuse_and_send()` every 0.1s (10Hz)
     - Prints status every 1s
     - Sleeps 0.01s

10. **Shutdown**:
    - Stops LIDAR motor and disconnects
    - Restores stderr
    - Closes devnull file

#### Key Functions:
- `check_vision_server()`: Validates Vision Server is running
- `read_depth_from_vision_server()`: Reads and validates depth data
- `connect_lidar()`: Connects to RPLidar S3
- `connect_pixhawk()`: Connects to Pixhawk via MAVLink
- `lidar_thread()`: Background thread for LIDAR scanning
- `realsense_thread_v9()`: Background thread for depth processing
- `fuse_and_send()`: Fuses sensors and sends to Pixhawk

#### Output Files:
- `/tmp/proximity_v9.json`: Fused proximity data, statistics

---

### 4. Simple Crop Monitor V9

**File**: `simple_crop_monitor_v9.py`  
**Component ID**: 198  
**Purpose**: Captures crop images from Vision Server, manages archive and dashboard buffer.

#### Step-by-Step Execution:

1. **Initialization** (`SimpleCropMonitor.__init__`):
   - Creates directories: `/tmp/crop_archive`, `/tmp/rover_vision`
   - Initializes counters: `capture_count`, `last_capture_time`
   - Sets `current_slot = 1` (rolling buffer 1-10)
   - Tracks `last_frame_number` for deduplication

2. **Vision Server Check** (`check_vision_server`):
   - Reads `/tmp/vision_v9/status.json`
   - Validates timestamp < 5 seconds old
   - Checks status == "RUNNING"
   - Returns True if available

3. **Source Availability** (`check_source_available`):
   - Waits up to 30 seconds for `/tmp/vision_v9/rgb_latest.jpg` and `.json`
   - Validates metadata timestamp < 2 seconds old
   - Returns True when source is ready

4. **Archive Management** (`manage_image_archive`):
   - Lists all `crop_*.jpg` files in archive directory
   - Sorts by modification time (oldest first)
   - Deletes oldest files until count < MAX_IMAGES (10)

5. **Image Capture** (`capture_image`):
   - Reads `/tmp/vision_v9/rgb_latest.json` (metadata)
   - Validates `frame_number` and `timestamp`
   - Skips if `frame_number == last_frame_number` (deduplication)
   - Validates frame age < 2 seconds
   - Updates `last_frame_number`
   - Reads image file (robust: tries buffer read, falls back to cv2.imread)
   - Validates image is not None/empty
   - **Archive write**:
     - Calls `manage_image_archive()` to ensure space
     - Generates timestamp: `YYYYMMDD_HHMMSS`
     - Saves to `/tmp/crop_archive/crop_TIMESTAMP.jpg` (quality 70)
   - **Dashboard write**:
     - Saves to `/tmp/rover_vision/CURRENT_SLOT.jpg` (quality 85)
     - Advances slot: `current_slot = (current_slot % 10) + 1`
   - Updates `capture_count`, `last_capture_time`
   - Writes `/tmp/crop_monitor_v9.json` (status):
     - Timestamp, capture_count, latest_image path
     - Image size, total archived, current_slot
     - last_frame_number, vision_server_connected
   - Returns True on success

6. **Main Loop** (`run`):
   - Checks Vision Server availability
   - Waits for source if not available
   - **Initialization**: Captures 10 images to initialize all dashboard slots
   - **Normal operation**:
     - Checks if `CAPTURE_INTERVAL` (10s) has elapsed
     - Calls `capture_image()`
     - Tracks consecutive failures
     - After 5 failures: Warns, checks Vision Server status
     - Sleeps 1s

#### Key Functions:
- `check_vision_server()`: Validates Vision Server is running
- `check_source_available()`: Waits for source image to be ready
- `manage_image_archive()`: Maintains rolling archive (max 10 images)
- `capture_image()`: Captures and saves image with deduplication

#### Output Files:
- `/tmp/crop_archive/crop_YYYYMMDD_HHMMSS.jpg`: Archived images (max 10)
- `/tmp/rover_vision/1.jpg` through `10.jpg`: Rolling dashboard buffer
- `/tmp/crop_monitor_v9.json`: Status file

---

### 5. Telemetry Dashboard V9

**File**: `telemetry_dashboard_v9.py`  
**Component ID**: 194  
**Purpose**: Flask web server providing real-time monitoring interface.

#### Step-by-Step Execution:

1. **Initialization**:
   - Creates Flask app with CORS support (if available)
   - Loads users from `/tmp/astra_dashboard_users.json` (default: admin/admin)
   - Initializes global `telemetry_data` dictionary

2. **Data Update Thread** (`update_telemetry_thread`):
   - Continuously reads shared files:
     - `/tmp/proximity_v9.json` → `telemetry_data['proximity']`
     - `/tmp/crop_monitor_v9.json` → `telemetry_data['system_status']['crop_monitor']`
     - `/tmp/vision_v9/status.json` → `telemetry_data['sensor_health']['realsense']`
   - Updates every 0.5 seconds
   - Handles missing files gracefully

3. **Flask Routes**:
   - **`/`**: Renders dashboard HTML (embedded template)
   - **`/api/telemetry`**: Returns JSON of current telemetry data
   - **`/api/stream/rgb`**: MJPEG stream from `/tmp/vision_v9/rgb_latest.jpg`
   - **`/api/stream/depth`**: MJPEG stream from `/tmp/vision_v9/depth_latest.jpg`
   - **`/api/stream/ir`**: MJPEG stream from `/tmp/vision_v9/ir_latest.jpg`
   - **`/login`**: Authentication endpoint
   - **`/logout`**: Logout endpoint
   - **`/signup`**: User registration (requires secret code)

4. **MJPEG Streaming** (`generate_mjpeg`):
   - Continuously reads image file
   - Encodes to JPEG
   - Yields MJPEG frame format: `--frame\r\nContent-Type: image/jpeg\r\n\r\n[data]\r\n`
   - Updates every ~0.067s (15 FPS)

5. **Main Execution**:
   - Starts data update thread
   - Runs Flask app on `0.0.0.0:8081` (or config port)

#### Key Functions:
- `update_telemetry_thread()`: Background thread for reading shared files
- `generate_mjpeg(image_path)`: Generator for MJPEG streaming
- Flask route handlers for HTML, API, streams

#### Endpoints:
- `GET /`: Dashboard HTML
- `GET /api/telemetry`: JSON telemetry data
- `GET /api/stream/rgb`: MJPEG RGB stream
- `GET /api/stream/depth`: MJPEG depth stream (pseudo-color)
- `GET /api/stream/ir`: MJPEG IR stream
- `POST /login`: Authentication
- `POST /logout`: Logout
- `POST /signup`: User registration

---

### 6. Data Relay V9

**File**: `data_relay_v9.py`  
**Component ID**: 197  
**Purpose**: Relays telemetry and images to remote dashboard via HTTP.

#### Step-by-Step Execution:

1. **Initialization** (`DataRelay.__init__`):
   - Loads dashboard IP/port from environment or defaults
   - Initializes telemetry dictionary (GPS, attitude, battery, proximity)
   - Sets image tracking variables

2. **Pixhawk Connection** (`connect_pixhawk`):
   - Tries config port, then `/dev/ttyACM0-3`
   - Creates MAVLink connection (baud 57600, component ID 197)
   - Waits for heartbeat (5s timeout)
   - Returns True on success

3. **Telemetry Update** (`update_telemetry`):
   - Reads MAVLink messages (non-blocking)
   - Updates telemetry based on message type:
     - `GPS_RAW_INT`: lat, lon, alt, fix_type
     - `ATTITUDE`: roll, pitch, yaw
     - `SYS_STATUS`: battery voltage, current, remaining

4. **Telemetry Send** (`send_telemetry`):
   - Reads `/tmp/proximity_v9.json` for proximity data
   - Adds timestamp, status: "OPERATIONAL"
   - POSTs to `{dashboard_url}/telemetry` (JSON)
   - Returns True on 200 response

5. **Image Send** (`send_image`):
   - Reads `/tmp/crop_latest.jpg` (or similar)
   - Validates file age < 90 seconds
   - Loads image with Pillow
   - Resizes thumbnail to max 1024x768 (LANCZOS)
   - Converts to JPEG (quality 75)
   - Base64 encodes
   - POSTs to `{dashboard_url}/image` (JSON with image_b64)
   - Returns True on 200 response

6. **Telemetry Thread** (`telemetry_thread`):
   - Continuously calls `update_telemetry()`
   - Calls `send_telemetry()` every 2 seconds
   - Sleeps 0.1s

7. **Image Thread** (`image_thread`):
   - Checks if 60 seconds have elapsed since last send
   - Calls `send_image()` if ready
   - Sleeps 5s

8. **Main Loop** (`run`):
   - Connects to Pixhawk (best effort)
   - Starts telemetry thread
   - Starts image thread
   - Prints status every 5 seconds

#### Key Functions:
- `connect_pixhawk()`: Connects to Pixhawk via MAVLink
- `update_telemetry()`: Reads MAVLink messages and updates telemetry
- `send_telemetry()`: POSTs telemetry to dashboard
- `send_image()`: POSTs image to dashboard
- `telemetry_thread()`: Background thread for telemetry
- `image_thread()`: Background thread for images

---

### 7. Parameter Application Tool

**File**: `tools/apply_params.py`  
**Purpose**: Applies Mission Planner `.param` file to Pixhawk via MAVLink.

#### Step-by-Step Execution:

1. **Parameter File Loading** (`load_param_file`):
   - Reads `.param` file line by line
   - Skips empty lines and comments (`#`)
   - Parses format: `PARAM_NAME,VALUE`
   - Converts value to float
   - Returns dictionary: `{param_name: value}`

2. **Parameter Application** (`apply_params`):
   - Waits for Pixhawk heartbeat (10s timeout)
   - **Optional backup**: Fetches all current parameters, saves to backup file
   - For each parameter:
     - Sends `PARAM_SET` message via MAVLink
     - Waits for `PARAM_VALUE` acknowledgment (2s timeout)
     - Validates readback value matches (within 0.001 tolerance)
     - Tracks applied/failed counts
     - Sleeps 0.05s between parameters
   - Returns (applied_count, failed_count)

3. **Main Execution** (`main`):
   - Parses command-line arguments:
     - `--port`: Pixhawk serial port (default: /dev/ttyACM0)
     - `--baud`: Baud rate (default: 57600)
     - `--file`: `.param` file path (required)
     - `--backup`: Backup file path (optional)
     - `--reboot`: Reboot Pixhawk after applying (optional)
   - Loads parameter file
   - Connects to Pixhawk
   - Applies parameters
   - Optionally reboots Pixhawk
   - Exits with error code if failures > 0

#### Key Functions:
- `load_param_file(param_file)`: Parses `.param` file
- `apply_params(master, params, backup_file)`: Applies parameters to Pixhawk

---

## Process Communication

### File-Based IPC (Inter-Process Communication)

**Vision Server → Others**:
- `/tmp/vision_v9/rgb_latest.jpg` + `.json` (RGB frames)
- `/tmp/vision_v9/depth_latest.bin` + `.json` (Depth data)
- `/tmp/vision_v9/ir_latest.jpg` + `.json` (IR frames)
- `/tmp/vision_v9/status.json` (Health status)

**Proximity Bridge → Others**:
- `/tmp/proximity_v9.json` (Fused proximity data)

**Crop Monitor → Others**:
- `/tmp/crop_archive/*.jpg` (Archived images)
- `/tmp/rover_vision/1-10.jpg` (Dashboard buffer)
- `/tmp/crop_monitor_v9.json` (Status)

### MAVLink Communication

**Proximity Bridge → Pixhawk**:
- `DISTANCE_SENSOR` messages (8 sectors, 10Hz)
- Component ID: 195

**Data Relay ↔ Pixhawk**:
- Reads: `GPS_RAW_INT`, `ATTITUDE`, `SYS_STATUS`
- Component ID: 197

### HTTP Communication

**Dashboard → Clients**:
- `GET /api/telemetry`: JSON telemetry
- `GET /api/stream/*`: MJPEG video streams

**Data Relay → Dashboard**:
- `POST /telemetry`: JSON telemetry (every 2s)
- `POST /image`: JSON with base64 image (every 60s)

---

## Data Flow

### Proximity Detection Flow:

```
RealSense Camera
    ↓
Vision Server (captures depth frames)
    ↓ (writes depth_latest.bin + metadata)
Proximity Bridge (reads depth data)
    ↓ (fuses with LIDAR)
Proximity Bridge (sends DISTANCE_SENSOR messages)
    ↓ (MAVLink)
Pixhawk (obstacle avoidance)
```

### Image Capture Flow:

```
RealSense Camera
    ↓
Vision Server (captures RGB frames)
    ↓ (writes rgb_latest.jpg + metadata)
Crop Monitor (reads image every 10s)
    ↓ (saves to archive + dashboard buffer)
Dashboard (displays via MJPEG stream)
```

### Telemetry Flow:

```
Pixhawk (GPS, attitude, battery)
    ↓ (MAVLink)
Data Relay (reads telemetry)
    ↓ (reads proximity_v9.json)
Data Relay (POSTs to dashboard API)
    ↓ (HTTP)
Remote Dashboard
```

---

## Summary

**V9 Key Improvements**:
1. **No Camera Conflicts**: Vision Server owns camera, others read files
2. **Frame Deduplication**: Metadata prevents processing same frame twice
3. **Atomic File Writes**: `.tmp` files + `os.replace()` prevents corrupted reads
4. **Health Monitoring**: Status files allow component health checks
5. **Process Locking**: Prevents duplicate Vision Server instances
6. **Cross-Platform**: Works on Unix and Windows (with fallbacks)

**Startup Order** (critical):
1. Vision Server (must start first)
2. Proximity Bridge (waits for Vision Server)
3. Crop Monitor (waits for Vision Server)
4. Dashboard (non-critical)
5. Data Relay (non-critical)

**File Locations**:
- Vision Server: `/tmp/vision_v9/`
- Proximity Bridge: `/tmp/proximity_v9.json`
- Crop Monitor: `/tmp/crop_archive/`, `/tmp/rover_vision/`
- Dashboard: Web interface on port 8081

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Project**: Astra NZ - V9

