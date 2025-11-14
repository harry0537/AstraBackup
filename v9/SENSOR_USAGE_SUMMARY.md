# Sensor Usage Summary - V9

## Overview

**RealSense Camera:**
- **Owner**: Vision Server (Component 196)
- **Purpose**: RGB/depth for crop monitoring and vision tasks
- **NOT used for obstacle detection** (LiDAR handles that)

**LiDAR (RPLidar S3):**
- **Owner**: Proximity Bridge (Component 195)
- **Purpose**: Full 360° obstacle detection for autonomous navigation
- **PRIMARY sensor** for all 8 sectors

---

## Vision Server (Component 196)

### RealSense Camera Usage

**What it does:**
- **Exclusive owner** of RealSense camera
- Captures RGB frames (424x240 @ 30fps)
- Captures depth frames (424x240 @ 30fps)
- Object detection (YOLO) on RGB frames
- Adaptive exposure control

**Output files** (in `/tmp/vision_v9/`):
- `rgb_latest.jpg` - RGB frame (JPEG)
- `rgb_latest.json` - RGB metadata
- `depth_latest.bin` - Depth data (binary)
- `depth_latest.json` - Depth metadata
- `status.json` - Server health status

**Who uses Vision Server output:**
1. **Crop Monitor** (Component 198)
   - Reads `rgb_latest.jpg` for crop monitoring
   - Captures images every 10 seconds
   - Uses frame deduplication

2. **Proximity Bridge** (Component 195)
   - Reads `depth_latest.bin` for **backup depth data only**
   - **NOT used for primary obstacle detection**
   - Only used if LiDAR unavailable for forward sectors

3. **Dashboard** (Component 194)
   - Displays RGB stream from Vision Server
   - Shows depth visualization
   - Object detection results

**Purpose:**
- ✅ **Crop monitoring** (RGB images)
- ✅ **Vision tasks** (object detection, RGB analysis)
- ✅ **Dashboard display** (live video stream)
- ❌ **NOT for obstacle detection** (that's LiDAR's job)

---

## Proximity Bridge (Component 195)

### LiDAR Usage (PRIMARY)

**What it does:**
- **PRIMARY sensor** for obstacle detection
- Provides **full 360° coverage** (8 sectors)
- Scans continuously for obstacles
- Sends distance data to Pixhawk via MAVLink

**8 Sectors:**
- Sector 0: Front (0°)
- Sector 1: Front-Right (45°)
- Sector 2: Right (90°)
- Sector 3: Rear-Right (135°)
- Sector 4: Rear (180°)
- Sector 5: Rear-Left (-135°)
- Sector 6: Left (-90°)
- Sector 7: Front-Left (-45°)

**Output:**
- Sends 8 `DISTANCE_SENSOR` messages to Pixhawk
- Updates at 10Hz
- Used by obstacle navigation script

**Purpose:**
- ✅ **Full 360° obstacle detection**
- ✅ **Autonomous navigation** (primary sensor)
- ✅ **All 8 sectors** use LiDAR data

### RealSense Depth Usage (BACKUP ONLY)

**What it does:**
- Reads depth data from Vision Server files
- **BACKUP only** - not used for primary detection
- Only used if LiDAR unavailable for forward sectors (0, 1, 7)

**When used:**
- Only if LiDAR data unavailable for forward sectors
- Only for forward sectors (0, 1, 7)
- **Never used if LiDAR is working**

**Purpose:**
- ⚠️ **Backup only** (if LiDAR fails)
- ❌ **NOT primary** for obstacle detection
- ✅ **Kept for Vision Server** (RGB/depth for crop monitoring)

---

## Data Flow

### Obstacle Detection Flow

```
RPLidar S3
    │
    │ (360° scan data)
    ▼
Proximity Bridge (Component 195)
    │
    │ (processes 8 sectors)
    ▼
    ├─→ All 8 sectors use LiDAR (PRIMARY)
    │
    └─→ RealSense depth (BACKUP only, if LiDAR unavailable)
    │
    ▼
8 DISTANCE_SENSOR messages → Pixhawk
    │
    ▼
Obstacle Navigation Script
    │
    ▼
Autonomous steering & throttle commands
```

### Vision/Crop Monitoring Flow

```
RealSense Camera
    │
    │ (RGB + Depth frames)
    ▼
Vision Server (Component 196)
    │
    │ (writes to /tmp/vision_v9/)
    ▼
    ├─→ rgb_latest.jpg
    │   └─→ Crop Monitor (Component 198) ← Uses for crop monitoring
    │
    ├─→ depth_latest.bin
    │   └─→ Proximity Bridge (backup only, not primary)
    │
    └─→ Dashboard (Component 194) ← Displays live stream
```

---

## Summary Table

| Sensor | Owner | Primary Use | Secondary Use | Obstacle Detection? |
|--------|-------|-------------|--------------|---------------------|
| **RealSense RGB** | Vision Server | Crop monitoring | Dashboard display | ❌ No |
| **RealSense Depth** | Vision Server | Crop monitoring | Backup for forward sectors | ⚠️ Backup only |
| **LiDAR** | Proximity Bridge | **360° obstacle detection** | None | ✅ **YES - PRIMARY** |

---

## Key Points

### RealSense Camera
- **Owned by**: Vision Server
- **Used for**: RGB/depth for crop monitoring, vision tasks, dashboard
- **NOT used for**: Primary obstacle detection

### LiDAR
- **Owned by**: Proximity Bridge
- **Used for**: **Full 360° obstacle detection** (all 8 sectors)
- **PRIMARY sensor** for autonomous navigation

### Separation of Concerns
- **Vision Server**: RealSense for vision/crop monitoring
- **Proximity Bridge**: LiDAR for obstacle detection
- **Clear separation**: Each sensor has its primary purpose

---

## Current Configuration

**Obstacle Detection:**
- ✅ **LiDAR**: All 8 sectors (360°)
- ⚠️ **RealSense depth**: Backup only (forward sectors, if LiDAR unavailable)

**Vision/Crop Monitoring:**
- ✅ **RealSense RGB**: Crop monitoring, dashboard
- ✅ **RealSense Depth**: Available for Vision Server tasks

**Result:**
- Full 360° obstacle detection with LiDAR
- RealSense kept for vision/crop monitoring
- No conflicts or dual-purpose confusion

