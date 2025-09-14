#!/usr/bin/env python3
"""
RPLidar S3 to MAVLink Bridge - FIXED for Front-Facing Mount
Routes data through MAVProxy for proper Mission Planner integration
"""

from rplidar import RPLidar
from pymavlink import mavutil
import time
import threading

# Configuration for front-facing RPLidar
lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000)

# FIXED: Send to MAVProxy (which forwards to Mission Planner)
mavlink = mavutil.mavlink_connection('udpout:127.0.0.1:14551')

num_sectors = 72
min_distance_cm = 20
max_distance_cm = 2500

def send_heartbeat():
    """Send periodic heartbeat to maintain MAVLink connection"""
    while True:
        mavlink.mav.heartbeat_send(
            type=mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
        time.sleep(1)

try:
    lidar.start_motor()
    print("🚀 LiDAR bridge started (Front-facing mount)")
    print("📡 Sending data to MAVProxy on port 14551")
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
    heartbeat_thread.start()
    
    for scan in lidar.iter_scans(max_buf_meas=1500):
        distances = [max_distance_cm] * num_sectors
        
        for quality, angle, distance_mm in scan:
            if quality < 10: 
                continue
                
            distance_cm = max(min_distance_cm, min(int(distance_mm/10), max_distance_cm))
            
            # FIXED: No coordinate rotation for front-facing mount
            # 0° = front, 90° = right, 180° = back, 270° = left
            sector = int((angle % 360) / 5)
            sector = max(0, min(sector, num_sectors-1))
            
            if distance_cm < distances[sector]:
                distances[sector] = distance_cm
        
        # Send distance sensor messages
        for sector_id, distance in enumerate(distances):
            mavlink.mav.distance_sensor_send(
                time_boot_ms=int(time.time() * 1000) & 0xFFFFFFFF,
                min_distance=min_distance_cm,
                max_distance=max_distance_cm,
                current_distance=distance,
                type=1,  # MAV_DISTANCE_SENSOR_LASER
                id=sector_id + 1,
                orientation=0,  # Let Mission Planner handle orientation
                covariance=0
            )
        
        print(f"📊 Sent {num_sectors} proximity sensors to MAVProxy", end='\r')
        time.sleep(0.1)  # 10Hz update rate
            
except KeyboardInterrupt:
    print("\n🛑 Stopping LiDAR bridge...")
finally:
    lidar.stop()
    lidar.disconnect()
    print("✅ LiDAR disconnected")