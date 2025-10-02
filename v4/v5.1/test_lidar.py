#!/usr/bin/env python3
"""
Test RPLidar connection and debug info/health methods
"""

import time
from rplidar import RPLidar

def test_lidar():
    print("Testing RPLidar connection...")
    
    # Try different ports
    ports = ['/dev/rplidar', '/dev/ttyUSB0', '/dev/ttyUSB1']
    
    for port in ports:
        try:
            print(f"Trying {port}...")
            lidar = RPLidar(port, baudrate=1000000, timeout=0.1)
            
            print("Getting info...")
            info = lidar.get_info()
            print(f"Info type: {type(info)}")
            print(f"Info value: {info}")
            
            print("Getting health...")
            health = lidar.get_health()
            print(f"Health type: {type(health)}")
            print(f"Health value: {health}")
            
            lidar.disconnect()
            print(f"✓ Success with {port}")
            return True
            
        except Exception as e:
            print(f"✗ Failed with {port}: {e}")
            continue
    
    return False

if __name__ == "__main__":
    test_lidar()
