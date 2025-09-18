#!/usr/bin/env python3
"""
Project Astra NZ - Hardware Check V4
Validates all hardware before system startup
"""

import os
import sys
import time
import subprocess

# Configuration (NEVER MODIFY)
LIDAR_PORT = '/dev/ttyUSB0'
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor} (need 3.8+)")
        return False

def check_permissions():
    """Check user permissions"""
    import grp
    try:
        user_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        if 'dialout' in user_groups:
            print("  ✓ User in dialout group")
            return True
        else:
            print("  ✗ User NOT in dialout group")
            print("    Run: sudo usermod -aG dialout $USER")
            print("    Then logout and login again")
            return False
    except Exception as e:
        print(f"  ⚠ Could not check groups: {e}")
        return False

def check_libraries():
    """Check required Python libraries"""
    libraries = {
        'rplidar': 'RPLidar',
        'pymavlink': 'MAVLink',
        'pyrealsense2': 'RealSense',
        'cv2': 'OpenCV',
        'numpy': 'NumPy',
        'PIL': 'Pillow',
        'requests': 'Requests',
        'flask': 'Flask'
    }
    
    all_ok = True
    for lib, name in libraries.items():
        try:
            if lib == 'cv2':
                import cv2
            elif lib == 'PIL':
                from PIL import Image
            else:
                __import__(lib)
            print(f"  ✓ {name} library")
        except ImportError:
            print(f"  ✗ {name} library missing")
            all_ok = False
            
    return all_ok

def check_rplidar():
    """Check RPLidar connection"""
    if not os.path.exists(LIDAR_PORT):
        print(f"  ✗ RPLidar not found at {LIDAR_PORT}")
        return False
        
    try:
        from rplidar import RPLidar
        lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=2)
        info = lidar.get_info()
        health = lidar.get_health()
        lidar.disconnect()
        
        print(f"  ✓ RPLidar S3 - Model: {info['model']}, Health: {health[0]}")
        return True
        
    except Exception as e:
        print(f"  ✗ RPLidar error: {e}")
        return False

def check_pixhawk():
    """Check Pixhawk connection"""
    # Check primary port
    if os.path.exists(PIXHAWK_PORT):
        print(f"  ✓ Pixhawk detected at configured port")
        return True
        
    # Check alternate ports
    for i in range(10):
        if os.path.exists(f'/dev/ttyACM{i}'):
            print(f"  ⚠ Pixhawk possibly at /dev/ttyACM{i}")
            print(f"    Update PIXHAWK_PORT in scripts if needed")
            return True
            
    print("  ✗ Pixhawk not detected")
    return False

def check_realsense():
    """Check RealSense camera"""
    try:
        import pyrealsense2 as rs
        ctx = rs.context()
        devices = ctx.query_devices()
        
        if len(devices) > 0:
            dev = devices[0]
            serial = dev.get_info(rs.camera_info.serial_number)
            name = dev.get_info(rs.camera_info.name)
            print(f"  ✓ RealSense {name} - Serial: {serial}")
            return True
        else:
            print("  ✗ No RealSense devices found")
            return False
            
    except Exception as e:
        print(f"  ✗ RealSense check failed: {e}")
        return False

def check_network():
    """Check network connectivity"""
    dashboard_ip = "10.244.77.186"
    
    # Check ZeroTier
    try:
        result = subprocess.run(['zerotier-cli', 'status'], 
                              capture_output=True, text=True, timeout=5)
        if 'ONLINE' in result.stdout:
            print("  ✓ ZeroTier online")
        else:
            print("  ⚠ ZeroTier not online")
    except:
        print("  ⚠ ZeroTier not installed or not running")
        
    # Ping dashboard
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '2', dashboard_ip],
                              capture_output=True, timeout=3)
        if result.returncode == 0:
            print(f"  ✓ Dashboard reachable at {dashboard_ip}")
            return True
        else:
            print(f"  ⚠ Dashboard not reachable at {dashboard_ip}")
            return False
    except:
        print(f"  ⚠ Could not ping dashboard")
        return False

def check_ports():
    """Check if required ports are available"""
    import socket
    
    ports = {
        14550: "MAVLink/Mission Planner",
        14551: "MAVProxy",
        5000: "Web interface",
        8080: "Dashboard"
    }
    
    all_ok = True
    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result != 0:  # Port is free
            print(f"  ✓ Port {port} available ({name})")
        else:
            print(f"  ⚠ Port {port} in use ({name})")
            all_ok = False
            
    return all_ok

def print_summary(results):
    """Print summary of checks"""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    categories = {
        'System': ['python', 'permissions', 'libraries'],
        'Hardware': ['rplidar', 'pixhawk', 'realsense'],
        'Network': ['network', 'ports']
    }
    
    for category, checks in categories.items():
        status = all(results.get(check, False) for check in checks)
        symbol = "✓" if status else "✗"
        print(f"{symbol} {category}")
        
    print("=" * 60)
    
    # Critical checks
    critical = ['python', 'permissions', 'libraries', 'rplidar', 'pixhawk']
    if all(results.get(check, False) for check in critical):
        print("\n🎉 System ready for Project Astra operation!")
        print("Run: python3 rover_manager_v4.py")
        return True
    else:
        print("\n⚠️  Critical issues detected")
        print("Please resolve issues before starting system")
        return False

def main():
    """Main execution"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - HARDWARE CHECK V4")
    print("=" * 60)
    
    results = {}
    
    print("\n[1/3] System Requirements")
    print("-" * 40)
    results['python'] = check_python_version()
    results['permissions'] = check_permissions()
    results['libraries'] = check_libraries()
    
    print("\n[2/3] Hardware Detection")
    print("-" * 40)
    results['rplidar'] = check_rplidar()
    results['pixhawk'] = check_pixhawk()
    results['realsense'] = check_realsense()
    
    print("\n[3/3] Network & Ports")
    print("-" * 40)
    results['network'] = check_network()
    results['ports'] = check_ports()
    
    return print_summary(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)