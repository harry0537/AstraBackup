#!/usr/bin/env python3
"""
Proximity Bridge Diagnostic Tool for Ubuntu/Linux
Checks common failure points that could cause the proximity bridge to stop
"""

import os
import sys
import json
import subprocess

# Use virtual environment Python if available
VENV_PATH = os.path.expanduser("~/rover_venv")
VENV_PYTHON = os.path.join(VENV_PATH, "bin", "python3")

def get_python_executable():
    """Get the correct Python executable (venv if available, system otherwise)"""
    if os.path.exists(VENV_PYTHON):
        return VENV_PYTHON
    else:
        return sys.executable
import time
import stat

def check_hardware_ports():
    """Check if required hardware ports exist"""
    print("=== HARDWARE PORTS ===")
    
    ports = {
        'LiDAR': '/dev/ttyUSB1',
        'Pixhawk': '/dev/ttyACM0'
    }
    
    for name, port in ports.items():
        exists = os.path.exists(port)
        print(f"  {name} ({port}): {'OK' if exists else 'MISSING'}")
        
        if exists:
            # Check permissions
            try:
                with open(port, 'r') as f:
                    pass
                print(f"    Permissions: OK Readable")
            except PermissionError:
                print(f"    Permissions: ERROR Permission denied")
            except Exception as e:
                print(f"    Permissions: ERROR {e}")
            
            # Check if it's a character device
            try:
                mode = os.stat(port).st_mode
                if stat.S_ISCHR(mode):
                    print(f"    Device type: OK Character device")
                else:
                    print(f"    Device type: ERROR Not a character device")
            except Exception as e:
                print(f"    Device type: ERROR {e}")

def check_user_permissions():
    """Check if user has required permissions"""
    print("\n=== USER PERMISSIONS ===")
    
    try:
        # Check if user is in dialout group
        result = subprocess.run(['groups'], capture_output=True, text=True)
        groups = result.stdout.strip()
        in_dialout = 'dialout' in groups
        print(f"  Dialout group: {'OK' if in_dialout else 'MISSING'}")
        if not in_dialout:
            print("    [FIX] Run: sudo usermod -a -G dialout $USER")
            print("    [FIX] Then logout and login again")
    except Exception as e:
        print(f"  Error checking groups: {e}")

def check_python_libraries():
    """Check if required Python libraries are available"""
    print("\n=== PYTHON LIBRARIES ===")
    
    libraries = [
        ('rplidar', 'RPLidar'),
        ('pymavlink', 'mavutil'),
        ('numpy', 'numpy'),
        ('pyrealsense2', 'rs')
    ]
    
    python_exe = get_python_executable()
    for lib_name, import_name in libraries:
        try:
            # Use venv Python to check if library is available
            result = subprocess.run(
                [python_exe, "-c", f"import {import_name}"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"  {lib_name}: OK Available")
            else:
                print(f"  {lib_name}: MISSING")
        except Exception as e:
            print(f"  {lib_name}: ERROR - {e}")

def check_config_file():
    """Check if configuration file exists and is valid"""
    print("\n=== CONFIGURATION ===")
    
    config_file = "rover_config_v8.json"
    if os.path.exists(config_file):
        print(f"  Config file: OK {config_file} exists")
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            print(f"  JSON valid: OK")
            
            # Check required fields
            required_fields = ['lidar_port', 'pixhawk_port', 'rover_ip']
            for field in required_fields:
                if field in config:
                    print(f"  {field}: OK {config[field]}")
                else:
                    print(f"  {field}: MISSING")
        except json.JSONDecodeError as e:
            print(f"  JSON valid: ERROR Invalid JSON: {e}")
        except Exception as e:
            print(f"  Config error: {e}")
    else:
        print(f"  Config file: MISSING {config_file} not found")

def check_temp_directory():
    """Check if temp directory is writable"""
    print("\n=== TEMP DIRECTORY ===")
    
    temp_file = "/tmp/proximity_v8.json"
    temp_dir = "/tmp"
    
    if os.path.exists(temp_dir):
        print(f"  /tmp exists: OK")
        try:
            # Test write permissions
            test_file = "/tmp/test_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print(f"  Write permissions: OK")
        except Exception as e:
            print(f"  Write permissions: ERROR {e}")
    else:
        print(f"  /tmp exists: MISSING")

def check_process_limits():
    """Check system resource limits"""
    print("\n=== SYSTEM RESOURCES ===")
    
    try:
        # Check file descriptor limit
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"  File descriptors: {soft}/{hard}")
        if soft < 1024:
            print("    [WARNING] Low file descriptor limit")
    except Exception as e:
        print(f"  Resource check error: {e}")

def check_usb_devices():
    """Check USB devices"""
    print("\n=== USB DEVICES ===")
    
    try:
        # List USB devices
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  USB devices found:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"    {line}")
        else:
            print("  lsusb command failed")
    except Exception as e:
        print(f"  USB check error: {e}")

def check_serial_devices():
    """Check serial devices"""
    print("\n=== SERIAL DEVICES ===")
    
    try:
        # List serial devices
        result = subprocess.run(['ls', '-la', '/dev/tty*'], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            relevant_devices = [line for line in lines if 'ttyUSB' in line or 'ttyACM' in line]
            if relevant_devices:
                print("  Relevant serial devices:")
                for device in relevant_devices:
                    print(f"    {device}")
            else:
                print("  No relevant serial devices found")
        else:
            print("  Serial device listing failed")
    except Exception as e:
        print(f"  Serial check error: {e}")

def check_running_processes():
    """Check if proximity bridge is already running"""
    print("\n=== RUNNING PROCESSES ===")
    
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            proximity_processes = [line for line in lines if 'combo_proximity_bridge' in line or 'proximity' in line]
            if proximity_processes:
                print("  Proximity bridge processes found:")
                for proc in proximity_processes:
                    print(f"    {proc}")
            else:
                print("  No proximity bridge processes running")
        else:
            print("  Process check failed")
    except Exception as e:
        print(f"  Process check error: {e}")

def main():
    print("PROXIMITY BRIDGE DIAGNOSTIC TOOL (UBUNTU)")
    print("=" * 50)
    
    check_hardware_ports()
    check_user_permissions()
    check_python_libraries()
    check_config_file()
    check_temp_directory()
    check_process_limits()
    check_usb_devices()
    check_serial_devices()
    check_running_processes()
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")
    print("\nIf you see any MISSING or ERROR marks above, those are likely causes")
    print("of the proximity bridge stopping.")

if __name__ == "__main__":
    main()
