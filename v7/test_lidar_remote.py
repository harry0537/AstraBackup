#!/usr/bin/env python3
"""
Simple LIDAR test for remote rover system
"""

import time
import sys

def test_lidar():
    """Test LIDAR connection on remote system"""
    print("Testing LIDAR connection...")
    
    try:
        from rplidar import RPLidar
        print("[OK] RPLidar library available")
    except ImportError as e:
        print(f"[ERROR] RPLidar library not found: {e}")
        print("Install with: pip install rplidar-roboticia")
        return False
    
    # Test the correct port
    lidar_port = '/dev/ttyUSB1'
    print(f"Testing LIDAR at {lidar_port}...")
    
    try:
        lidar = RPLidar(lidar_port, baudrate=1000000, timeout=1)
        
        # Get device info
        info = lidar.get_info()
        health = lidar.get_health()
        
        print(f"[OK] Connected to {lidar_port}")
        print(f"  Model: {info['model']}")
        print(f"  Firmware: {info['firmware']}")
        print(f"  Hardware: {info['hardware']}")
        print(f"  Health: {health[0]}")
        
        # Test basic scan
        print("Testing basic scan...")
        lidar.start_motor()
        time.sleep(1)
        
        # Try to get one measurement
        scan_count = 0
        for scan in lidar.iter_scans(max_buf_meas=10):
            scan_count += 1
            print(f"[OK] Scan {scan_count}: {len(scan)} points")
            if scan_count >= 2:  # Get a couple of scans
                break
        
        lidar.stop()
        lidar.stop_motor()
        lidar.disconnect()
        
        print("[OK] LIDAR test successful!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to connect to {lidar_port}: {e}")
        return False

if __name__ == "__main__":
    print("LIDAR Test for Remote Rover System")
    print("=" * 40)
    
    success = test_lidar()
    
    if success:
        print("\n[SUCCESS] LIDAR is working correctly!")
    else:
        print("\n[ERROR] LIDAR needs troubleshooting")
        print("\nTroubleshooting steps:")
        print("1. Check USB connection")
        print("2. Check if device is at /dev/ttyUSB1")
        print("3. Check permissions: ls -l /dev/ttyUSB1")
        print("4. Try: sudo chmod 666 /dev/ttyUSB1")
