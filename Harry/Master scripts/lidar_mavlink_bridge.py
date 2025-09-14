#!/usr/bin/env python3
"""
RPLidar S3 to MAVLink Bridge - Core Working Version
Uses the exact proven configuration from user testing
"""

from rplidar import RPLidar
from pymavlink import mavutil
import time

# Configuration - matches your working setup
lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000)
mavlink = mavutil.mavlink_connection('udpout:127.0.0.1:14550')

num_sectors = 72
min_distance_cm = 20
max_distance_cm = 2500

try:
    lidar.start_motor()
    print("🚀 LiDAR bridge started - Press Ctrl+C to stop")
ECHO is off.
    for scan in lidar.iter_scans(max_buf_meas=1500):
        distances = [max_distance_cm]*num_sectors
ECHO is off.
        for quality, angle, distance_mm in scan:
            if quality < 10: 
                continue
            distance_cm = max(min_distance_cm, min(int(distance_mm/10), max_distance_cm))
            sector = int(((90-angle)%360)/5)
            sector = max(0, min(sector, num_sectors-1))
            if distance_cm < distances[sector]:
                distances[sector] = distance_cm
ECHO is off.
        for sector_id, d in enumerate(distances):
            mavlink.mav.distance_sensor_send(
                time_boot_ms=int(time.time()*1000)&0xFFFFFFFF,
                min_distance=min_distance_cm,
                max_distance=max_distance_cm,
                current_distance=d,
                type=1,
                id=sector_id+1,
                orientation=0,
                covariance=0
            )
ECHO is off.
except KeyboardInterrupt:
    print("\\n🛑 Stopping LiDAR bridge...")
finally:
    lidar.stop()
    lidar.disconnect()
    print("✅ LiDAR disconnected")
