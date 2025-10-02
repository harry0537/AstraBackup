#!/usr/bin/env python3
"""
Quick test to verify MAVLink messages are flowing
"""

from pymavlink import mavutil
import time

print("🎯 Testing MAVLink connection...")
try:
    mavlink = mavutil.mavlink_connection('udpin:127.0.0.1:14550')
    print("Waiting for DISTANCE_SENSOR messages...")
    print("^(Make sure lidar_mavlink_bridge.py is running^)")
ECHO is off.
    for i in range(30):  # Wait 30 seconds max
        msg = mavlink.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=1)
        if msg:
            print(f"✅ Received data from sensor {msg.id}: {msg.current_distance}cm")
            break
        print(f"Waiting... {i+1}/30")
    else:
        print("❌ No DISTANCE_SENSOR messages received")
ECHO is off.
except Exception as e:
    print(f"❌ Error: {e}")
