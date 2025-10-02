#!/usr/bin/env python3
"""
Project Astra NZ - Hardware Detection and Verification Script v4
Checks all sensors and connections before system startup
Ubuntu 24.04 compatible with improved device detection
"""

import os
import sys
import time
import subprocess

# Check for required libraries
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

try:
    from rplidar import RPLidar
    RPLIDAR_AVAILABLE = True
except ImportError:
    RPLIDAR_AVAILABLE = False

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False

def check_device_permissions():
    """Check device permissions for Ubuntu 24.04"""
    print("Checking device permissions...")
    
    # Check dialout group membership
    try:
        groups_output = subprocess.check_output(['groups'], universal_newlines=True)
        if 'dialout' in groups_output:
            print("  ✓ User is in dialout group")
        else:
            print("  ⚠ User not in dialout group - run: sudo usermod -aG dialout $USER")
    except:
        print("  ✗ Could not check group membership")
    
    # Check device files exist and permissions
    devices_to_check = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyACM1']
    for device in devices_to_check:
        if os.path.exists(device):
            stat_info = os.stat(device)
            permissions = oct(stat_info.st_mode)[-3:]
            print(f"  {device}: exists, permissions {permissions}")
        else:
            print(f"  {device}: not found")

def check_rplidar():
    """Check RPLidar S3 connection and health"""
    print("Checking RPLidar S3...")
    
    if not RPLIDAR_AVAILABLE:
        print("  ✗ RPLidar library not installed - run: pip install rplidar")
        return False
    
    # Check device file
    if not os.path.exists('/dev/ttyUSB0'):
        print("  ✗ RPLidar not found at /dev/ttyUSB0")
        print("    Check USB connection and try: ls /dev/ttyUSB*")
        return False
    
    # Test permissions
    if not os.access('/dev/ttyUSB0', os.R_OK | os.W_OK):
        print("  ✗ No read/write permission for /dev/ttyUSB0")
        print("    Run: sudo chmod 666 /dev/ttyUSB0")
        return False
    
    try:
        print("  Connecting to RPLidar...")
        lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000, timeout=3)
        
        print("  Getting device info...")
        info = lidar.get_info()
        health = lidar.get_health()
        
        # Test short scan
        print("  Testing scan capability...")
        lidar.start_scan()
        time.sleep(0.5)
        lidar.stop()
        lidar.disconnect()
        
        print(f"  ✓ RPLidar S3 connected")
        print(f"    Model: {info['model']}, Firmware: {info['fw']}")
        print(f"    Health: {health[0]}")
        return True
        
    except Exception as e:
        print(f"  ✗ RPLidar connection failed: {e}")
        print("    Try: sudo chmod 666 /dev/ttyUSB0")
        return False

def check_realsense():
    """Check Intel RealSense D435i connection"""
    print("Checking Intel RealSense D435i...")
    
    if not REALSENSE_AVAILABLE:
        print("  ✗ RealSense library not installed - run: pip install pyrealsense2")
        return False
    
    try:
        print("  Detecting RealSense devices...")
        ctx = rs.context()
        devices = ctx.query_devices()
        
        if len(devices) == 0:
            print("  ✗ No RealSense devices detected")
            print("    Check USB connection (use USB 3.0 port)")
            return False
        
        device = devices[0]
        print(f"  Device found: {device.get_info(rs.camera_info.name)}")
        print(f"  Serial: {device.get_info(rs.camera_info.serial_number)}")
        
        # Test pipeline configuration
        print("  Testing camera streams...")
        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        
        pipeline.start(config)
        
        # Test frame capture
        for i in range(5):
            frames = pipeline.wait_for_frames(timeout_ms=2000)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            
            if color_frame and depth_frame:
                break
        
        pipeline.stop()
        
        if color_frame and depth_frame:
            print("  ✓ RealSense D435i connected and streaming")
            print(f"    Color: {color_frame.get_width()}x{color_frame.get_height()}")
            print(f"    Depth: {depth_frame.get_width()}x{depth_frame.get_height()}")
            return True
        else:
            print("  ✗ Failed to capture test frames")
            return False
            
    except Exception as e:
        print(f"  ✗ RealSense connection failed: {e}")
        print("    Ensure device is connected to USB 3.0 port")
        return False

def find_pixhawk_device():
    """Find Pixhawk device across multiple possible locations"""
    possible_devices = []
    
    # Check by-id directory first (most reliable)
    by_id_path = '/dev/serial/by-id'
    if os.path.exists(by_id_path):
        for device in os.listdir(by_id_path):
            if any(keyword in device for keyword in ['Pixhawk', 'Holybro', 'Cube', 'ArduPilot']):
                full_path = os.path.join(by_id_path, device)
                possible_devices.append(('by-id', full_path))
    
    # Check ttyACM devices
    for i in range(10):
        device = f'/dev/ttyACM{i}'
        if os.path.exists(device):
            possible_devices.append(('ttyACM', device))
    
    # Check ttyUSB devices (some flight controllers)
    for i in range(1, 5):  # Skip ttyUSB0 (usually RPLidar)
        device = f'/dev/ttyUSB{i}'
        if os.path.exists(device):
            possible_devices.append(('ttyUSB', device))
    
    return possible_devices

def check_pixhawk():
    """Check Pixhawk connection and ArduPilot communication"""
    print("Checking Pixhawk 6C connection...")
    
    if not MAVLINK_AVAILABLE:
        print("  ✗ MAVLink library not installed - run: pip install pymavlink")
        return False
    
    # Find possible Pixhawk devices
    devices = find_pixhawk_device()
    
    if not devices:
        print("  ✗ No potential Pixhawk devices found")
        print("    Check USB connection and try: ls /dev/ttyACM* /dev/ttyUSB*")
        return False
    
    print(f"  Found {len(devices)} potential device(s)")
    
    # Test each device
    for device_type, device_path in devices:
        print(f"  Testing {device_path} ({device_type})...")
        
        if not os.access(device_path, os.R_OK | os.W_OK):
            print(f"    No permission - run: sudo chmod 666 {device_path}")
            continue
        
        try:
            # Test connection with timeout
            mavlink = mavutil.mavlink_connection(device_path, baud=57600)
            mavlink.wait_heartbeat(timeout=10)
            
            # Get system info
            msg = mavlink.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg:
                print(f"  ✓ Pixhawk connected at {device_path}")
                print(f"    System ID: {msg.get_srcSystem()}")
                print(f"    Component ID: {msg.get_srcComponent()}")
                print(f"    Vehicle Type: {msg.type}")
                print(f"    Autopilot: {msg.autopilot}")
                mavlink.close()
                return True
                
        except Exception as e:
            print(f"    Connection failed: {e}")
            continue
    
    print("  ✗ Could not establish MAVLink connection")
    print("    Verify ArduPilot firmware is installed and configured")
    return False

def check_system_resources():
    """Check system resources and performance"""
    print("Checking system resources...")
    
    try:
        # Check CPU usage
        load_avg = os.getloadavg()
        print(f"  CPU Load: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
        
        # Check memory usage
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        
        for line in meminfo.split('\n'):
            if 'MemTotal:' in line:
                total_kb = int(line.split()[1])
                total_gb = total_kb / 1024 / 1024
                print(f"  Total RAM: {total_gb:.1f} GB")
            elif 'MemAvailable:' in line:
                avail_kb = int(line.split()[1])
                avail_gb = avail_kb / 1024 / 1024
                print(f"  Available RAM: {avail_gb:.1f} GB")
        
        # Check disk space
        statvfs = os.statvfs('/')
        total_space = statvfs.f_frsize * statvfs.f_blocks / 1024 / 1024 / 1024
        free_space = statvfs.f_frsize * statvfs.f_bavail / 1024 / 1024 / 1024
        print(f"  Disk Space: {free_space:.1f} GB free of {total_space:.1f} GB total")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Could not check system resources: {e}")
        return False

def check_python_environment():
    """Check Python environment and required packages"""
    print("Checking Python environment...")
    
    # Python version
    python_version = sys.version.split()[0]
    print(f"  Python version: {python_version}")
    
    if sys.version_info < (3, 8):
        print("  ⚠ Python 3.8+ recommended")
    else:
        print("  ✓ Python version OK")
    
    # Check virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("  ✓ Virtual environment active")
    else:
        print("  ⚠ Not in virtual environment")
    
    # Check key packages
    packages = {
        'rplidar': RPLIDAR_AVAILABLE,
        'pyrealsense2': REALSENSE_AVAILABLE,  
        'pymavlink': MAVLINK_AVAILABLE
    }
    
    for package, available in packages.items():
        status = "✓" if available else "✗"
        print(f"  {package}: {status}")
    
    return all(packages.values())

def main():
    """Main hardware check routine"""
    print("=" * 60)
    print("Project Astra NZ - Hardware Check v4")
    print("Ubuntu 24.04 Compatible")
    print("=" * 60)
    print()
    
    # Run all checks
    checks = []
    
    checks.append(("Device Permissions", check_device_permissions))
    checks.append(("Python Environment", check_python_environment))
    checks.append(("System Resources", check_system_resources))
    checks.append(("RPLidar S3", check_rplidar))
    checks.append(("RealSense D435i", check_realsense)) 
    checks.append(("Pixhawk 6C", check_pixhawk))
    
    # Execute checks
    results = {}
    for check_name, check_func in checks:
        print()
        if check_func == check_device_permissions or check_func == check_system_resources:
            check_func()  # These don't return boolean
            results[check_name] = True
        else:
            results[check_name] = check_func()
    
    # Summary
    print("\n" + "=" * 60)
    print("HARDWARE CHECK SUMMARY")
    print("=" * 60)
    
    sensor_checks = ["RPLidar S3", "RealSense D435i", "Pixhawk 6C"]
    all_sensors_ok = True
    
    for check_name, result in results.items():
        status = "✓" if result else "✗"
        print(f"{check_name:20} {status}")
        if check_name in sensor_checks and not result:
            all_sensors_ok = False
    
    print()
    if all_sensors_ok and results.get("Python Environment", False):
        print("🎉 ALL SYSTEMS GO!")
        print("Project Astra hardware ready for operation")
        print()
        print("Next steps:")
        print("1. Start proximity system: python3 combo_proximity_bridge_v4.py")
        print("2. Start data relay: python3 rover_data_relay_v1.py")
        print("3. Connect Mission Planner via UDP:14550")
        return True
    else:
        print("⚠️  HARDWARE ISSUES DETECTED")
        print("Please resolve issues before proceeding")
        print()
        print("Common solutions:")
        print("- Run: sudo usermod -aG dialout $USER && logout")
        print("- Run: sudo chmod 666 /dev/ttyUSB0 /dev/ttyACM0")
        print("- Check USB connections and try different ports")
        print("- Install missing packages: pip install rplidar pymavlink pyrealsense2")
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nHardware check interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error during hardware check: {e}")
        sys.exit(1)
