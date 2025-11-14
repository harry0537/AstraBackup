# Documentation Corrections Needed

## Critical Corrections

### 1. LiDAR Model Name (Multiple Sections)

**Current (INCORRECT):**
- "RPLiDAR A1" or "RPLiDAR A1/C3"

**Should be:**
- **"RPLiDAR S3"** (this is what's actually used in the codebase)

**Sections to fix:**
- Section 9.7.1: "RealSense D435i Camera and RPLiDAR A1/C3—"
- Section 9.7.1: "RPLiDAR A1 Key Features"
- Section 9.8: "RPLiDAR A1 sensor"
- Any other mentions of "A1" or "A1/C3"

---

### 2. Sensor Usage for Obstacle Detection (Sections 9.7, 9.8)

**Current (MISLEADING):**
- Document suggests RealSense and LiDAR are used equally for obstacle detection
- Mentions "fusing" both sensors together

**Should clarify:**
- **LiDAR (RPLiDAR S3) is PRIMARY** for all 8 sectors (full 360° obstacle detection)
- **RealSense is for Vision Server only** (RGB/depth for crop monitoring)
- **RealSense depth is BACKUP only** (forward sectors 0, 1, 7, only if LiDAR unavailable)

**Sections to fix:**
- Section 9.7.1: Add clarification about sensor roles
- Section 9.7.2: Update fusion logic description
- Section 9.8: Clarify that LiDAR is primary for obstacle avoidance

---

### 3. Section 9.7.1 - RealSense D435i Camera and RPLiDAR A1/C3

**Current text:**
```
Obstacle detection was implemented using a combination of the Intel RealSense D435i depth camera and the RPLiDAR A1 2D LiDAR scanner. Together, they provide a complementary perception system — the RealSense captures close-range depth and colour data, while the LiDAR provides 360° spatial awareness around the vehicle.
```

**Should be:**
```
Obstacle detection was implemented using the RPLiDAR S3 2D LiDAR scanner as the PRIMARY sensor for full 360° obstacle detection. The Intel RealSense D435i depth camera is used exclusively by the Vision Server for RGB/depth capture for crop monitoring. RealSense depth data is available as a backup only for forward sectors (0, 1, 7) if LiDAR becomes unavailable, but LiDAR provides the primary obstacle detection for all 8 sectors.
```

**Also update:**
- Change "RPLiDAR A1 Key Features" to "RPLiDAR S3 Key Features"
- Update detection range if different (S3 may have different specs than A1)

---

### 4. Section 9.7.2 - Obstacle Detection Pipeline

**Current text:**
```
The pipeline performs the following steps:

1. Depth Stream Capture:
The script initialises the RealSense D435i camera and RPLiDAR sensors and begins to stream data simultaneously.

2. Data Filtering and Fusion:
Depth frames from the RealSense are filtered to remove outliers and invalid pixels, while LiDAR scans are downsampled to remove redundant points.

The two data sources are fused to create a composite obstacle map that prioritises LiDAR data for lateral detection and RealSense depth data for frontal accuracy.
```

**Should be:**
```
The pipeline performs the following steps:

1. LiDAR Stream Capture:
The script initialises the RPLiDAR S3 sensor and begins continuous 360° scanning. The RealSense camera is NOT accessed directly by the proximity bridge (it's owned by Vision Server).

2. Data Processing:
LiDAR scans are processed to create 8 sector distances (0° to 360° in 45° increments). Each sector represents the minimum distance detected in that angular range.

3. Fusion Logic (Backup Only):
For all 8 sectors, LiDAR data is used as PRIMARY. RealSense depth data (read from Vision Server files) is used as BACKUP only for forward sectors (0, 1, 7) if LiDAR data is unavailable for those sectors. In normal operation, all sectors use LiDAR exclusively.
```

---

### 5. Section 9.8 - Obstacle Avoidance

**Current text:**
```
The object detection and avoidance system was implemented using the BendyRuler algorithm provided by ArduPilot, enabling the UGV to dynamically adjust its path when the onboard proximity sensors detected obstacles — the Intel RealSense D435i and RPLiDAR A1 mounted at the front of the UGV.
```

**Should be:**
```
The object detection and avoidance system was implemented using the BendyRuler algorithm provided by ArduPilot, enabling the UGV to dynamically adjust its path when the onboard proximity sensors detected obstacles. The RPLiDAR S3 provides PRIMARY obstacle detection for all 8 sectors (full 360° coverage), while the Intel RealSense D435i is used exclusively by the Vision Server for crop monitoring. RealSense depth data is available as backup only for forward sectors if LiDAR becomes unavailable.
```

---

### 6. Section 9.7.3 - System Integration

**Current text:**
```
This integration enables the UGV to:

• Continuously detect obstacles within its surroundings using both RealSense D435i and RPLiDAR A1 sensors.
```

**Should be:**
```
This integration enables the UGV to:

• Continuously detect obstacles within its surroundings using the RPLiDAR S3 sensor for full 360° coverage (PRIMARY).
• RealSense D435i is used by Vision Server for RGB/depth capture for crop monitoring (not for obstacle detection).
• RealSense depth data is available as backup only for forward sectors if LiDAR unavailable.
```

---

### 7. Section 11.5 - Obstacle Detection and Avoidance (Results)

**Current text:**
```
Obstacle detection was implemented through the combined use of the Intel RealSense D435i depth camera and a 2D RPLiDAR A1 sensor. The RealSense provided high-resolution depth data and RGB imagery, while LiDAR complemented detection by identifying reflective and non-textured surfaces.
```

**Should be:**
```
Obstacle detection was implemented using the RPLiDAR S3 sensor as the PRIMARY sensor for full 360° obstacle detection. The Intel RealSense D435i depth camera is used exclusively by the Vision Server for RGB/depth capture for crop monitoring. RealSense depth data is available as backup only for forward sectors if LiDAR becomes unavailable. The LiDAR provides complete 360° coverage, detecting obstacles in all directions around the vehicle.
```

---

### 8. Glossary Entry

**Current:**
```
Light Detection and Ranging (LiDAR):
A sensor that emits laser pulses to measure distance and map surroundings. The RPLiDAR A1 was used in this project for obstacle detection and navigation assistance.
```

**Should be:**
```
Light Detection and Ranging (LiDAR):
A sensor that emits laser pulses to measure distance and map surroundings. The RPLiDAR S3 was used in this project as the PRIMARY sensor for full 360° obstacle detection and navigation assistance.
```

---

## Summary of Changes

1. **Replace all "RPLiDAR A1" or "RPLiDAR A1/C3" with "RPLiDAR S3"**
2. **Clarify that LiDAR is PRIMARY for obstacle detection (all 8 sectors)**
3. **Clarify that RealSense is for Vision Server only (crop monitoring)**
4. **Clarify that RealSense depth is BACKUP only (forward sectors, if LiDAR unavailable)**
5. **Update fusion logic description to reflect LiDAR-first approach**

---

## Additional Notes

- The current architecture uses **RPLiDAR S3** (not A1)
- LiDAR provides **full 360° coverage** for all 8 sectors
- RealSense is **NOT used for primary obstacle detection** - it's for Vision Server
- RealSense depth is **backup only** for forward sectors if LiDAR unavailable
- This separation was implemented to avoid camera conflicts and provide better 360° coverage

---

## Recommended Wording

When describing the obstacle detection system, use:

**"The obstacle detection system uses the RPLiDAR S3 as the PRIMARY sensor for full 360° obstacle detection across all 8 sectors. The Intel RealSense D435i depth camera is used exclusively by the Vision Server for RGB/depth capture for crop monitoring and vision tasks. RealSense depth data is available as a backup only for forward sectors (0, 1, 7) if LiDAR becomes unavailable, but in normal operation, all sectors use LiDAR exclusively."**

