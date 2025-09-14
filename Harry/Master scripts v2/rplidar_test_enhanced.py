#!/usr/bin/env python3
"""
RPLidar S3 Test Script - Enhanced for Front-Facing Mount Validation
"""

from rplidar import RPLidar
import time
import sys

def test_rplidar():
    """Test RPLidar connection with front-facing validation"""
    
    try:
        print("Connecting to RPLidar S3 on /dev/ttyUSB0...")
        lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000)
        
        # Get device info
        print("\n=== Device Information ===")
        info = lidar.get_info()
        print(f"Model: {info['model']}")
        print(f"Firmware: {info['firmware']}")
        print(f"Hardware: {info['hardware']}")
        print(f"Serial: {info['serialnumber']}")
        
        # Get health status
        print("\n=== Health Status ===")
        health = lidar.get_health()
        print(f"Status: {health[0]}")
        print(f"Error Code: {health[1]}")
        
        if health[0] != 'Good':
            print("WARNING: Lidar health is not good!")
            return False
        
        # Test scans with front-facing analysis
        print("\n=== Testing Front-Facing Scans ===")
        print("Starting motor and analyzing front sector (350°-10°)...")
        lidar.start_motor()
        
        scan_count = 0
        front_detections = []
        
        for scan in lidar.iter_scans(max_buf_meas=1500):
            scan_count += 1
            valid_points = 0
            front_points = 0
            
            for quality, angle, distance_mm in scan:
                if quality > 10:
                    valid_points += 1
                    # Check front sector (350° to 10°)
                    if angle >= 350 or angle <= 10:
                        front_points += 1
                        if distance_mm < 2000:  # Less than 2m
                            front_detections.append((angle, distance_mm))
            
            print(f"Scan {scan_count}: {len(scan)} total, {valid_points} valid, {front_points} front sector")
            
            if front_detections:
                closest = min(front_detections, key=lambda x: x[1])
                print(f"  🎯 Front obstacle at {closest[0]:.1f}°: {closest[1]/10:.1f}cm")
            
            if scan_count >= 5:
                break
        
        print(f"\n✅ RPLidar S3 front-facing test completed!")
        print(f"📊 Detected {len(front_detections)} front obstacles across {scan_count} scans")
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing RPLidar: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check if device is connected: ls /dev/ttyUSB*")
        print("2. Check permissions: sudo usermod -aG dialout $USER")
        print("3. Check power supply to the lidar")
        print("4. Try: sudo chmod 666 /dev/ttyUSB0")
        print("5. Verify front-facing mount orientation")
        return False
        
    finally:
        try:
            lidar.stop()
            lidar.disconnect()
            print("Lidar disconnected safely.")
        except:
            pass

if __name__ == "__main__":
    print("RPLidar S3 Front-Facing Connection Test")
    print("=" * 40)
    
    success = test_rplidar()
    
    if success:
        print("\n🎉 All tests passed! Your front-facing RPLidar S3 is ready!")
        print("🚀 Next: Run the fixed lidar_mavlink_bridge.py")
        sys.exit(0)
    else:
        print("\n💥 Tests failed. Please check the troubleshooting tips above.")
        sys.exit(1)