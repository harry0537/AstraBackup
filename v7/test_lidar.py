#!/usr/bin/env python3
"""
RPLidar Detection Test Script
Tests for LiDAR connection and basic functionality
"""

import sys
import time
import os

def test_lidar_connection():
    """Test LiDAR connection and basic functionality"""
    print("=" * 50)
    print("RPLidar Detection Test")
    print("=" * 50)
    
    # Test 1: Check if rplidar library is available
    try:
        from rplidar import RPLidar
        print("[OK] RPLidar library available")
    except ImportError as e:
        print(f"[ERROR] RPLidar library not found: {e}")
        print("Install with: pip install rplidar-roboticia")
        return False
    
    # Test 2: Check common LiDAR ports
    common_ports = [
        '/dev/ttyUSB0',  # Linux
        '/dev/ttyUSB1',  # Linux
        '/dev/ttyACM0',  # Linux
        'COM3',          # Windows
        'COM4',          # Windows
        'COM5',          # Windows
        'COM6',          # Windows
    ]
    
    print("\nChecking for LiDAR on common ports...")
    found_ports = []
    
    for port in common_ports:
        if os.path.exists(port):
            print(f"[OK] Found device at {port}")
            found_ports.append(port)
        else:
            print(f"[NO] No device at {port}")
    
    if not found_ports:
        print("\n[ERROR] No LiDAR devices found!")
        print("\nTroubleshooting steps:")
        print("1. Check USB connection")
        print("2. Install CP210x drivers")
        print("3. Check Device Manager for 'Silicon Labs' device")
        print("4. Try different USB port")
        return False
    
    # Test 3: Try to connect to each found port
    print(f"\nTesting connection to found ports...")
    
    for port in found_ports:
        try:
            print(f"Testing {port}...")
            lidar = RPLidar(port, baudrate=1000000, timeout=1)
            
            # Get device info
            info = lidar.get_info()
            health = lidar.get_health()
            
            print(f"✓ Connected to {port}")
            print(f"  Model: {info['model']}")
            print(f"  Firmware: {info['firmware']}")
            print(f"  Hardware: {info['hardware']}")
            print(f"  Health: {health[0]}")
            
            # Test basic scan
            print("  Testing basic scan...")
            lidar.start_motor()
            time.sleep(1)
            
            # Try to get one measurement
            for i, scan in enumerate(lidar.iter_scans(max_buf_meas=10)):
                if i >= 1:  # Just get one scan
                    break
                print(f"  ✓ Scan successful: {len(scan)} points")
            
            lidar.stop()
            lidar.stop_motor()
            lidar.disconnect()
            
            print(f"✓ {port} is working correctly!")
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to {port}: {e}")
            continue
    
    print("\n❌ Could not connect to any LiDAR device")
    return False

def check_windows_ports():
    """Check Windows COM ports specifically"""
    print("\n" + "=" * 50)
    print("Windows COM Port Check")
    print("=" * 50)
    
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("No COM ports found")
            return
        
        print("Available COM ports:")
        for port in ports:
            print(f"  {port.device}: {port.description}")
            if 'Silicon Labs' in port.description or 'CP210' in port.description:
                print(f"    ✓ This looks like RPLidar!")
    except ImportError:
        print("pyserial not available for port scanning")
    except Exception as e:
        print(f"Error scanning ports: {e}")

if __name__ == "__main__":
    print("RPLidar Detection and Test Script")
    print("=" * 50)
    
    # Check Windows ports first
    check_windows_ports()
    
    # Test LiDAR connection
    success = test_lidar_connection()
    
    if success:
        print("\n🎉 LiDAR is working correctly!")
    else:
        print("\n❌ LiDAR needs troubleshooting")
        print("\nNext steps:")
        print("1. Check physical USB connection")
        print("2. Install CP210x drivers from Silicon Labs")
        print("3. Check Device Manager for unrecognized devices")
        print("4. Try different USB port or powered hub")
