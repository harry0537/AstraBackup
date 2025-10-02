#!/usr/bin/env python3
"""
RPLidar S3 Test Script
Tests connection and basic functionality of SLAMTEC RPLidar S3
"""

from rplidar import RPLidar
import time
import sys

def test_rplidar():
    """Test RPLidar connection and basic functionality"""
ECHO is off.
    # Try to connect to the lidar
    try:
        print("Connecting to RPLidar S3 on /dev/ttyUSB0...")
        lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000)
ECHO is off.
        # Get device info
        print("\\n=== Device Information ===")
        info = lidar.get_info()
        print(f"Model: {info['model']}")
        print(f"Firmware: {info['firmware']}")
        print(f"Hardware: {info['hardware']}")
        print(f"Serial: {info['serialnumber']}")
ECHO is off.
        # Get health status
        print("\\n=== Health Status ===")
        health = lidar.get_health()
        print(f"Status: {health[0]}")
        print(f"Error Code: {health[1]}")
ECHO is off.
        if health[0] != 'Good':
            print("WARNING: Lidar health is not good!")
            return False
ECHO is off.
        # Test a few scans
        print("\\n=== Testing Scans ===")
        print("Starting motor and collecting scan data...")
        lidar.start_motor()
ECHO is off.
        scan_count = 0
        for scan in lidar.iter_scans(max_buf_meas=1500):
            scan_count += 1
            valid_points = len([point for point in scan if point[0] > 10])  # Quality > 10
            print(f"Scan {scan_count}: {len^(scan^)} total points, {valid_points} valid points")
ECHO is off.
            if scan_count >= 3:  # Test just a few scans
                break
ECHO is off.
        print("\\n✅ RPLidar S3 test completed successfully!")
        return True
ECHO is off.
    except Exception as e:
        print(f"\\n❌ Error testing RPLidar: {e}")
        print("\\nTroubleshooting tips:")
        print("1. Check if device is connected: ls /dev/ttyUSB*")
        print("2. Check permissions: sudo usermod -aG dialout $USER")
        print("3. Check power supply to the lidar")
        print("4. Try: sudo chmod 666 /dev/ttyUSB0")
        return False
ECHO is off.
    finally:
        try:
            lidar.stop()
            lidar.disconnect()
            print("Lidar disconnected safely.")
        except:
            pass

if __name__ == "__main__":
    print("RPLidar S3 Connection Test")
    print("=" * 30)
ECHO is off.
    success = test_rplidar()
ECHO is off.
    if success:
        print("\\n🎉 All tests passed! Your RPLidar S3 is ready to use.")
        sys.exit(0)
    else:
        print("\\n💥 Tests failed. Please check the troubleshooting tips above.")
        sys.exit(1)
