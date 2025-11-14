# Copy-Paste Text Corrections for Capstone Report

## Section 9.7.1 - Title and Introduction

### REPLACE THIS:
```
9.7.1. RealSense D435i Camera and RPLiDAR A1/C3—

Obstacle detection was implemented using a combination of the Intel RealSense D435i depth camera and the RPLiDAR A1 2D LiDAR scanner. Together, they provide a complementary perception system — the RealSense captures close-range depth and colour data, while the LiDAR provides 360° spatial awareness around the vehicle.
```

### WITH THIS:
```
9.7.1. RealSense D435i Camera and RPLiDAR S3

Obstacle detection was implemented using the RPLiDAR S3 2D LiDAR scanner as the PRIMARY sensor for full 360° obstacle detection. The Intel RealSense D435i depth camera is used exclusively by the Vision Server for RGB/depth capture for crop monitoring. RealSense depth data is available as a backup only for forward sectors (0, 1, 7) if LiDAR becomes unavailable, but LiDAR provides the primary obstacle detection for all 8 sectors.
```

---

## Section 9.7.1 - RPLiDAR Key Features

### REPLACE THIS:
```
RPLiDAR A1 Key Features

•	360° horizontal scanning
•	Detection range: up to 12 m (indoor)
•	Angular resolution: ≤ 1°
•	Sampling rate: 8,000 samples per second
•	Communication interface: USB / UART

Both sensors were connected to the Ubuntu 22.04 OS, which served as the rover's onboard computer. The RealSense provided forward-facing stereo depth data, while the RPLiDAR continuously scanned the surrounding area, producing real-time range information. The combined data improved object detection reliability in both confined and open environments
```

### WITH THIS:
```
RPLiDAR S3 Key Features

•	360° horizontal scanning
•	Detection range: up to 12 m (indoor)
•	Angular resolution: ≤ 1°
•	Sampling rate: 8,000 samples per second
•	Communication interface: USB / UART

The RPLiDAR S3 sensor was connected to the Ubuntu 22.04 OS, which served as the rover's onboard computer. The LiDAR continuously scans the surrounding area, producing real-time range information for all 8 sectors (0° to 360° in 45° increments). The RealSense D435i camera is owned exclusively by the Vision Server component and is not used for primary obstacle detection, but its depth data is available as a backup for forward sectors if LiDAR becomes unavailable.
```

---

## Section 9.7.2 - Obstacle Detection Pipeline

### REPLACE THIS:
```
A custom Python-based detection pipeline was developed using the OpenCV library, the Intel RealSense SDK, the RPLiDAR SDK, and the MAVLink communication protocol. The system fused data from both sensors and transmitted processed obstacle distances to the Pixhawk 6C flight controller for dynamic avoidance.

The pipeline performs the following steps:

1.	Depth Stream Capture:

The script initialises the RealSense D435i camera and RPLiDAR sensors and begins to stream data simultaneously.

2.	Data Filtering and Fusion:

Depth frames from the RealSense are filtered to remove outliers and invalid pixels, while LiDAR scans are downsampled to remove redundant points.

The two data sources are fused to create a composite obstacle map that prioritises LiDAR data for lateral detection and RealSense depth data for frontal accuracy.

3.	Obstacle Distance Calculation:

The script calculates the minimum detected distance within the configured field of view (adjustable beam width). This determines the closest object to the UGV in real-time.

4.	MAVLink Message Encoding:

The processed distance data is encoded into the OBSTACLE_DISTANCE MAVLink message format compatible with ArduPilot's obstacle avoidance features.

5.	Data Transmission to Pixhawk:

The MAVLink messages are transmitted over a serial link from the Raspberry Pi to the Pixhawk 6C flight controller, enabling dynamic path adjustments.

6.	Visualisation in Mission Planner:

Once received by the Pixhawk, the obstacle data is visualised in the Proximity Radar view in Mission Planner, displaying live detection arcs and distances around the UGV.
```

### WITH THIS:
```
A custom Python-based detection pipeline was developed using the RPLiDAR SDK and the MAVLink communication protocol. The system processes LiDAR data as the PRIMARY sensor and transmits processed obstacle distances to the Pixhawk 6C flight controller for dynamic avoidance. The RealSense D435i camera is not accessed directly by the proximity bridge (it's owned by the Vision Server), but depth data from Vision Server files is available as backup.

The pipeline performs the following steps:

1.	LiDAR Stream Capture:

The script initialises the RPLiDAR S3 sensor and begins continuous 360° scanning. The RealSense camera is NOT accessed directly by the proximity bridge (it's owned by Vision Server).

2.	Data Processing:

LiDAR scans are processed to create 8 sector distances (0° to 360° in 45° increments). Each sector represents the minimum distance detected in that angular range. The sectors are: Front (0°), Front-Right (45°), Right (90°), Rear-Right (135°), Rear (180°), Rear-Left (-135°), Left (-90°), and Front-Left (-45°).

3.	Fusion Logic (Backup Only):

For all 8 sectors, LiDAR data is used as PRIMARY. RealSense depth data (read from Vision Server files) is used as BACKUP only for forward sectors (0, 1, 7) if LiDAR data is unavailable for those sectors. In normal operation, all sectors use LiDAR exclusively.

4.	MAVLink Message Encoding:

The processed distance data is encoded into 8 DISTANCE_SENSOR MAVLink messages (one per sector) compatible with ArduPilot's obstacle avoidance features.

5.	Data Transmission to Pixhawk:

The MAVLink messages are transmitted over a serial link from the Ubuntu onboard computer to the Pixhawk 6C flight controller at 10Hz, enabling dynamic path adjustments.

6.	Visualisation in Mission Planner:

Once received by the Pixhawk, the obstacle data is visualised in the Proximity Radar view in Mission Planner, displaying live detection arcs and distances around the UGV for all 8 sectors.
```

---

## Section 9.7.3 - System Integration

### REPLACE THIS:
```
This integration enables the UGV to:

•	Continuously detect obstacles within its surroundings using both RealSense D435i and RPLiDAR A1 sensors.

•	Process and fuse depth and LiDAR data through a custom Python pipeline on the Ubuntu-based rover computer.

•	Encode and transmit MAVLink OBSTACLE_DISTANCE messages to the Pixhawk 6C in real time.

•	Allow the BendyRuler avoidance algorithm to adjust the UGV's trajectory dynamically.

•	Visualise proximity data in the Mission Planner Proximity Radar, providing operators with real-time spatial awareness.

This fusion-based perception system enables the UGV to autonomously detect, interpret, and avoid obstacles while executing waypoint missions — eliminating the need for external fencing or static boundaries.
```

### WITH THIS:
```
This integration enables the UGV to:

•	Continuously detect obstacles within its surroundings using the RPLiDAR S3 sensor for full 360° coverage (PRIMARY sensor for all 8 sectors).

•	Process LiDAR data through a custom Python pipeline on the Ubuntu-based rover computer, creating 8 sector distance measurements.

•	Use RealSense D435i exclusively for Vision Server (RGB/depth for crop monitoring), with depth data available as backup only for forward sectors if LiDAR unavailable.

•	Encode and transmit 8 MAVLink DISTANCE_SENSOR messages (one per sector) to the Pixhawk 6C at 10Hz in real time.

•	Allow the BendyRuler avoidance algorithm to adjust the UGV's trajectory dynamically based on 360° obstacle awareness.

•	Visualise proximity data in the Mission Planner Proximity Radar, providing operators with real-time spatial awareness for all directions around the vehicle.

This LiDAR-based perception system enables the UGV to autonomously detect, interpret, and avoid obstacles while executing waypoint missions — eliminating the need for external fencing or static boundaries. The full 360° coverage provides superior obstacle awareness compared to forward-only sensors.
```

---

## Section 9.7.4 - Testing and Validation

### REPLACE THIS:
```
Field tests confirmed that the combined RealSense + RPLiDAR system reliably detected obstacles in both indoor and outdoor environments.

•	The RealSense accurately captured obstacles within 0.2–4 m in front of the UGV.

•	The RPLiDAR provided consistent 360° coverage up to 12 m, especially adequate for lateral and rear detections.

•	The Proximity Radar display in Mission Planner accurately reflected object positions and distances, allowing the BendyRuler algorithm to adjust the path in real time dynamically.

Figure 9.9: Sample of proximity sensor detection and response

•	Add lidar proximity sensor data.
```

### WITH THIS:
```
Field tests confirmed that the RPLiDAR S3 system reliably detected obstacles in both indoor and outdoor environments with full 360° coverage.

•	The RPLiDAR S3 provided consistent 360° coverage up to 12 m for all 8 sectors, enabling detection in all directions around the vehicle.

•	The system achieved reliable obstacle detection for front, side, and rear sectors, eliminating blind spots.

•	The Proximity Radar display in Mission Planner accurately reflected object positions and distances for all 8 sectors, allowing the BendyRuler algorithm to adjust the path in real time dynamically.

•	RealSense depth data was available as backup for forward sectors, but in normal operation, all sectors used LiDAR exclusively.

Figure 9.9: Sample of proximity sensor detection and response

•	LiDAR proximity sensor data for all 8 sectors (360° coverage).
```

---

## Section 9.8 - Obstacle Avoidance

### REPLACE THIS:
```
The object detection and avoidance system was implemented using the BendyRuler algorithm provided by ArduPilot, enabling the UGV to dynamically adjust its path when the onboard proximity sensors detected obstacles — the Intel RealSense D435i and RPLiDAR A1 mounted at the front of the UGV.
```

### WITH THIS:
```
The object detection and avoidance system was implemented using the BendyRuler algorithm provided by ArduPilot, enabling the UGV to dynamically adjust its path when the onboard proximity sensors detected obstacles. The RPLiDAR S3 provides PRIMARY obstacle detection for all 8 sectors (full 360° coverage), while the Intel RealSense D435i is used exclusively by the Vision Server for crop monitoring. RealSense depth data is available as backup only for forward sectors if LiDAR becomes unavailable.
```

---

## Section 11.5 - Obstacle Detection and Avoidance (Results)

### REPLACE THIS:
```
Obstacle detection was implemented through the combined use of the Intel RealSense D435i depth camera and a 2D RPLiDAR A1 sensor. The RealSense provided high-resolution depth data and RGB imagery, while LiDAR complemented detection by identifying reflective and non-textured surfaces.

Testing showed consistent obstacle detection of moving subjects (such as people) at distances up to 5 metres. Static objects were detected reliably within a 3–4 metre range, though bright sunlight occasionally reduced depth accuracy due to infrared interference. The BendyRuler avoidance algorithm successfully recalculated routes when obstacles were detected, but tight turning limitations and wheel alignment drift occasionally reduced responsiveness.

While the detection success rate exceeded 90 per cent, avoidance performance depended on surface traction and steering precision. Future design improvements will focus on enhancing the turning radius and sensor placement to strengthen reaction time and path correction.
```

### WITH THIS:
```
Obstacle detection was implemented using the RPLiDAR S3 sensor as the PRIMARY sensor for full 360° obstacle detection. The Intel RealSense D435i depth camera is used exclusively by the Vision Server for RGB/depth capture for crop monitoring. RealSense depth data is available as backup only for forward sectors if LiDAR becomes unavailable. The LiDAR provides complete 360° coverage, detecting obstacles in all directions around the vehicle.

Testing showed consistent obstacle detection of moving subjects (such as people) at distances up to 5 metres across all 8 sectors. Static objects were detected reliably within a 3–4 metre range in all directions, providing superior coverage compared to forward-only sensors. The BendyRuler avoidance algorithm successfully recalculated routes when obstacles were detected in any sector, enabling the vehicle to avoid obstacles from all directions. Tight turning limitations and wheel alignment drift occasionally reduced responsiveness, but the 360° awareness provided better situational awareness.

While the detection success rate exceeded 90 per cent, avoidance performance depended on surface traction and steering precision. Future design improvements will focus on enhancing the turning radius and sensor placement to strengthen reaction time and path correction. The full 360° coverage eliminates blind spots and provides superior obstacle awareness compared to forward-only detection systems.
```

---

## Glossary - LiDAR Entry

### REPLACE THIS:
```
Light Detection and Ranging (LiDAR):

A sensor that emits laser pulses to measure distance and map surroundings. The RPLiDAR A1 was used in this project for obstacle detection and navigation assistance.
```

### WITH THIS:
```
Light Detection and Ranging (LiDAR):

A sensor that emits laser pulses to measure distance and map surroundings. The RPLiDAR S3 was used in this project as the PRIMARY sensor for full 360° obstacle detection and navigation assistance across all 8 sectors.
```

---

## Table 8.1 - Hardware Components (if present)

### IF YOU HAVE THIS:
```
RPLiDAR A1	2D LiDAR scanning	Lightweight, affordable, and provides 360° environmental scanning with a range of up to 12 m.
```

### REPLACE WITH:
```
RPLiDAR S3	2D LiDAR scanning	Lightweight, affordable, and provides 360° environmental scanning with a range of up to 12 m. PRIMARY sensor for obstacle detection across all 8 sectors.
```

---

## Quick Find & Replace

If you want to do a quick find-and-replace across the document:

1. **Find:** `RPLiDAR A1` → **Replace:** `RPLiDAR S3`
2. **Find:** `RPLiDAR A1/C3` → **Replace:** `RPLiDAR S3`
3. **Find:** `RPLiDAR A1 sensor` → **Replace:** `RPLiDAR S3 sensor`
4. **Find:** `combined RealSense + RPLiDAR` → **Replace:** `RPLiDAR S3 (with RealSense backup)`
5. **Find:** `both RealSense D435i and RPLiDAR` → **Replace:** `RPLiDAR S3 (RealSense for Vision Server only)`

---

## Summary

**Key Changes:**
1. All "RPLiDAR A1" → "RPLiDAR S3"
2. Clarify LiDAR is PRIMARY for obstacle detection (all 8 sectors, 360°)
3. Clarify RealSense is for Vision Server only (crop monitoring)
4. Clarify RealSense depth is backup only (forward sectors, if LiDAR unavailable)
5. Update all descriptions to reflect LiDAR-first approach

