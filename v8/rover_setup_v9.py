#!/usr/bin/env python3
"""
Project Astra NZ - Rover Setup V9
Modern setup for rover system with v9 components and space optimization
Streamlined setup with enhanced hardware detection and configuration

FUNCTIONALITY:
- Automated installation and configuration of the complete V9 rover system
- Creates and configures virtual environment with all dependencies
- Auto-detects and configures all hardware components (LiDAR, Pixhawk, RealSense)
- Sets up device permissions and udev rules for hardware access
- Configures network settings and dashboard access
- Sets up storage optimization and log rotation
- Optional systemd service creation for auto-start

SETUP PROCESS:
1. Python Dependencies: Installs all required packages in virtual environment
2. Permissions: Configures device permissions and udev rules for hardware
3. Network: Detects rover IP and configures network settings
4. Hardware: Auto-detects and configures LiDAR, Pixhawk, RealSense
5. Storage: Sets up log rotation and storage optimization
6. Service: Optional systemd service creation for auto-start

HARDWARE DETECTION:
- RPLidar: Tests multiple ports and validates LiDAR connection
- Pixhawk: Detects autopilot via MAVLink heartbeat
- RealSense: Tests multiple camera configurations for optimal settings
- Permissions: Verifies user is in dialout group for device access
- Storage: Checks available disk space for image storage

CONFIGURATION OUTPUT:
- Config File: rover_config_v9.json with all detected settings
- Virtual Environment: ~/rover_venv with all dependencies installed
- Device Rules: /etc/udev/rules.d/99-astra-v9.rules for hardware access
- Log Rotation: /etc/logrotate.d/astra-v9 for storage management
- Service: /etc/systemd/system/astra-rover-v9.service for auto-start

USAGE:
- Run: python3 rover_setup_v9.py
- For service creation: sudo python3 rover_setup_v9.py
- Automatically detects hardware and creates optimal configuration
"""

import os
import sys
import subprocess
import json
import socket
import glob
import time

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

CONFIG_FILE = "rover_config_v9.json"  # Main configuration file

def run_cmd(cmd, check=False):
    """Run command and return success"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, check=check)
        return result.returncode == 0
    except:
        return False

def check_sudo():
    """Check if running with sudo"""
    return os.geteuid() == 0

def install_dependencies():
    """Install Python dependencies for V9 with proper virtual environment handling"""
    print("\n[1/4] Python Dependencies")
    print("-" * 40)

    packages = {
        'rplidar-roboticia': 'rplidar',
        'pymavlink': 'pymavlink',
        'pyrealsense2': 'pyrealsense2',
        'opencv-python': 'cv2',
        'numpy': 'numpy',
        'Pillow': 'PIL',
        'requests': 'requests',
        'flask': 'flask',
        'flask-cors': 'flask_cors'
    }

    venv_path = os.path.expanduser("~/rover_venv")
    venv_pip = os.path.join(venv_path, "bin", "pip")
    venv_python = os.path.join(venv_path, "bin", "python3")
    venv_activate = os.path.join(venv_path, "bin", "activate")

    # Check if we're already in the virtual environment
    if 'VIRTUAL_ENV' in os.environ:
        print(f"✓ Already in virtual environment: {os.environ['VIRTUAL_ENV']}")
    else:
        print("⚠ Not in virtual environment - will create and use rover_venv")

    # Create virtual environment if it doesn't exist
    if not os.path.exists(venv_path):
        print("Creating virtual environment...")
        if run_cmd(f"python3 -m venv {venv_path}"):
            print("✓ Virtual environment created")
        else:
            print("✗ Failed to create virtual environment")
            return False
    else:
        print("✓ Virtual environment exists")

    # Verify virtual environment is working
    if not os.path.exists(venv_python):
        print("✗ Virtual environment Python not found")
        return False

    # Check and install packages
    print("Checking/installing packages...")
    for pkg, import_name in packages.items():
        try:
            result = subprocess.run(
                [venv_python, "-c", f"import {import_name}"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"  ✓ {pkg}")
            else:
                raise ImportError()
        except:
            print(f"  Installing {pkg}...", end='')
            if run_cmd(f"{venv_pip} install {pkg}"):
                print(" ✓")
            else:
                print(" ✗")
                print(f"    [ERROR] Failed to install {pkg}")
                print(f"    [INFO] Try: {venv_pip} install {pkg}")

    print("✓ Dependencies ready")
    print(f"\n[IMPORTANT] Virtual environment created at: {venv_path}")
    print("To activate it manually, run:")
    print(f"  source {venv_activate}")
    print("Or use the full path to Python:")
    print(f"  {venv_python} rover_manager_v9.py")
    
    return True

def setup_permissions():
    """Configure device permissions"""
    print("\n[2/4] Permissions")
    print("-" * 40)

    user = os.environ.get('USER', 'pi')

    # Check dialout group
    result = subprocess.run(['groups', user], capture_output=True, text=True)
    if 'dialout' not in result.stdout:
        print(f"⚠ User {user} not in dialout group")
        print(f"  Run: sudo usermod -aG dialout {user}")
        print("  Then logout and login")
    else:
        print(f"✓ User {user} in dialout group")

    # Create udev rules for V9
    rules_file = "/etc/udev/rules.d/99-astra-v9.rules"
    rules = """# Project Astra NZ V9
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2dae", MODE="0666", SYMLINK+="pixhawk"
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", MODE="0666"
SUBSYSTEM=="video4linux", ATTRS{idVendor}=="8086", MODE="0666"
"""

    if os.path.exists(rules_file):
        print("✓ Device rules exist")
    elif check_sudo():
        print("Creating udev rules...")
        with open(rules_file, 'w') as f:
            f.write(rules)
        run_cmd("udevadm control --reload-rules")
        run_cmd("udevadm trigger")
        print("✓ Device rules created")
    else:
        print("⚠ Udev rules need sudo to create")
        print("  Run: sudo python3 rover_setup_v9.py")

def configure_network():
    """Configure network settings for V9"""
    print("\n[3/4] Network")
    print("-" * 40)

    config = {
        "dashboard_ip": "0.0.0.0",
        "dashboard_port": 8081,
        "mavlink_port": 14550
    }

    # Detect local IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        config["rover_ip"] = local_ip
        print(f"✓ Rover IP: {local_ip}")
    except:
        print("⚠ Could not detect IP")

    # Test dashboard connectivity
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '2',
                               config['rover_ip']],
                              capture_output=True, timeout=3)
        if result.returncode == 0:
            print(f"✓ Network reachable at {config['rover_ip']}")
        else:
            print(f"⚠ Network not reachable")
    except:
        print("⚠ Cannot ping network")

    return config

def detect_hardware():
    """Auto-detect all hardware and return addresses for V9"""
    print("\n[4/4] Hardware Detection")
    print("-" * 40)

    hardware = {
        'lidar_port': None,
        'pixhawk_port': None,
        'realsense_available': False,
        'realsense_config': None
    }

    # Detect LIDAR
    print("Detecting RPLidar...")
    lidar_candidates = [
        '/dev/rplidar',  # Symlink from udev rules
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3'
    ]

    for port in lidar_candidates:
        if os.path.exists(port):
            test_lidar = None
            try:
                from rplidar import RPLidar
                test_lidar = RPLidar(port, baudrate=1000000, timeout=1)
                info = test_lidar.get_info()
                test_lidar.disconnect()
                hardware['lidar_port'] = port
                print(f"✓ RPLidar detected at {port} (Model: {info['model']})")
                break
            except Exception as e:
                if test_lidar:
                    try:
                        test_lidar.disconnect()
                    except:
                        pass
                continue

    if not hardware['lidar_port']:
        print("⚠ RPLidar not found")

    # Detect Pixhawk
    print("Detecting Pixhawk...")
    pixhawk_candidates = [
        '/dev/pixhawk',  # Symlink from udev rules
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3',
        '/dev/serial/by-id/usb-Holybro_Pixhawk6C_*',
        '/dev/serial/by-id/usb-3D_Robotics_PX4_*'
    ]

    for pattern in pixhawk_candidates:
        if '*' in pattern:
            matches = glob.glob(pattern)
            for port in matches:
                if os.path.exists(port):
                    test_conn = None
                    try:
                        from pymavlink import mavutil
                        test_conn = mavutil.mavlink_connection(port, baud=57600, timeout=2)
                        test_conn.wait_heartbeat(timeout=2)
                        test_conn.close()
                        hardware['pixhawk_port'] = port
                        print(f"✓ Pixhawk detected at {port}")
                        break
                    except Exception as e:
                        if test_conn:
                            try:
                                test_conn.close()
                            except:
                                pass
                        continue
        else:
            if os.path.exists(pattern):
                test_conn = None
                try:
                    from pymavlink import mavutil
                    test_conn = mavutil.mavlink_connection(pattern, baud=57600, timeout=2)
                    test_conn.wait_heartbeat(timeout=2)
                    test_conn.close()
                    hardware['pixhawk_port'] = pattern
                    print(f"✓ Pixhawk detected at {pattern}")
                    break
                except Exception as e:
                    if test_conn:
                        try:
                            test_conn.close()
                        except:
                            pass
                    continue

    if not hardware['pixhawk_port']:
        print("⚠ Pixhawk not found")

    # Detect RealSense
    print("Detecting RealSense...")
    try:
        import pyrealsense2 as rs
        hardware['realsense_available'] = True

        # Test different configurations to find working one
        configs_to_try = [
            (rs.stream.depth, 640, 480, rs.format.z16, 15),
            (rs.stream.depth, 424, 240, rs.format.z16, 15),
            (rs.stream.depth, 320, 240, rs.format.z16, 15),
        ]

        for i, (stream, width, height, format, fps) in enumerate(configs_to_try):
            pipeline = None
            try:
                pipeline = rs.pipeline()
                config = rs.config()
                config.enable_stream(stream, width, height, format, fps)
                pipeline.start(config)

                # Test frame capture
                for attempt in range(5):
                    try:
                        frames = pipeline.wait_for_frames(timeout_ms=2000)
                        if frames.get_depth_frame():
                            hardware['realsense_config'] = {
                                'width': width,
                                'height': height,
                                'fps': fps
                            }
                            print(f"✓ RealSense detected - {width}x{height} @ {fps}fps")
                            pipeline.stop()
                            pipeline = None
                            break
                    except:
                        if attempt < 4:
                            time.sleep(0.5)
                        continue

                if pipeline:
                    try:
                        pipeline.stop()
                    except:
                        pass
                    pipeline = None

                if hardware['realsense_config']:
                    break

            except Exception as e:
                if pipeline:
                    try:
                        pipeline.stop()
                    except:
                        pass
                time.sleep(1)
                continue

        if not hardware['realsense_config']:
            print("⚠ RealSense detected but no working configuration found")
        else:
            print("✓ RealSense configuration optimized")

    except ImportError:
        print("⚠ RealSense library not found")

    return hardware

def setup_storage_optimization():
    """Setup storage optimization for V9"""
    print("\n[Storage Optimization]")
    print("-" * 40)

    # Create crop images directory
    crop_dir = "/tmp/crop_images"
    os.makedirs(crop_dir, exist_ok=True)
    print(f"✓ Created crop images directory: {crop_dir}")

    # Check available space
    try:
        result = subprocess.run(['df', '-h', '/tmp'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    available = parts[3]
                    print(f"✓ Available space in /tmp: {available}")
    except:
        print("⚠ Could not check available space")

    # Set up log rotation
    logrotate_config = """# Project Astra NZ V9 Log Rotation
/tmp/crop_images/*.jpg {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
"""
    
    if check_sudo():
        with open('/etc/logrotate.d/astra-v9', 'w') as f:
            f.write(logrotate_config)
        print("✓ Log rotation configured")
    else:
        print("⚠ Log rotation needs sudo to configure")

def create_service():
    """Create systemd service for V9"""
    print("\n[Optional] Auto-Start Service")
    print("-" * 40)

    response = input("Enable auto-start on boot? [y/N]: ")
    if response.lower() == 'y':
        if not check_sudo():
            print("⚠ Need sudo to create service")
            print("  Run: sudo python3 rover_setup_v9.py")
            return

        service = f"""[Unit]
Description=Project Astra NZ Rover V9
After=network.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
WorkingDirectory={os.getcwd()}
Environment="PATH={os.path.expanduser('~/rover_venv/bin')}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart={os.path.expanduser('~/rover_venv/bin/python3')} {os.getcwd()}/rover_manager_v9.py --auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        with open('/etc/systemd/system/astra-rover-v9.service', 'w') as f:
            f.write(service)
        run_cmd("systemctl daemon-reload")
        run_cmd("systemctl enable astra-rover-v9.service")
        print("✓ Auto-start enabled")
        print("  Start: sudo systemctl start astra-rover-v9")
        print("  Stop:  sudo systemctl stop astra-rover-v9")

def print_summary():
    """Print setup summary for V9"""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE - V9")
    print("=" * 60)

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        print(f"\nDashboard: {config['dashboard_ip']}:{config['dashboard_port']}")
        print(f"MAVLink:   Port {config['mavlink_port']}")
        print(f"Rover IP:  {config.get('rover_ip', 'Unknown')}")

    print("\nV9 Features:")
    print("• Modern compact dashboard (no scrolling)")
    print("• Space-optimized crop monitor (40 images max)")
    print("• Enhanced GPS and power monitoring")
    print("• Improved system resource management")

    print("\nNext Steps:")
    print("1. Activate virtual environment:")
    print("   source ~/rover_venv/bin/activate")
    print("   Or use: ./activate_rover_venv.sh")
    print("")
    print("2. Run: python3 rover_manager_v9.py")
    print("3. View: http://0.0.0.0:8081")
    print("4. Network: http://172.25.77.186:8081")
    print("\n✓ Ready to start!")

def main():
    """
    Main execution function for V9 rover system setup
    
    This function orchestrates the complete setup process:
    1. Installs Python dependencies in virtual environment
    2. Configures device permissions and udev rules
    3. Detects and configures network settings
    4. Auto-detects and configures all hardware components
    5. Sets up storage optimization and log rotation
    6. Creates comprehensive configuration file
    7. Optionally creates systemd service for auto-start
    8. Displays setup summary and next steps
    
    The setup process is designed to be:
    - Automated: Minimal user interaction required
    - Robust: Handles missing hardware gracefully
    - Comprehensive: Configures all system components
    - Optimized: Sets up space-saving and performance features
    """
    print("=" * 60)
    print("PROJECT ASTRA NZ - ROVER SETUP V9")
    print("=" * 60)

    # Step 1: Install Python dependencies in virtual environment
    install_dependencies()
    
    # Step 2: Configure device permissions and udev rules
    setup_permissions()
    
    # Step 3: Detect and configure network settings
    network_config = configure_network()
    
    # Step 4: Auto-detect and configure hardware components
    hardware_config = detect_hardware()
    
    # Step 5: Set up storage optimization and log rotation
    setup_storage_optimization()

    # Merge all configurations with V9 defaults
    # This creates a comprehensive configuration file with all detected settings
    full_config = {
        **network_config,      # Network and IP settings
        **hardware_config,     # Hardware ports and configurations
        "crop_monitor": {      # Space-optimized image capture settings
            "interval": 60,    # Capture every 60 seconds
            "max_images": 40,  # Maximum 40 images stored
            "quality": 60      # 60% JPEG quality for space efficiency
        },
        "proximity_bridge": {  # Sensor fusion settings
            "sector_count": 8,           # 8 proximity sectors
            "max_distance_cm": 2500,     # 25m maximum detection range
            "mavlink_enabled": True      # Enable MAVLink communication
        },
        "data_relay": {        # Data transmission settings
            "enabled": True,            # Enable data relay
            "relay_interval": 30        # 30-second relay interval
        },
        "telemetry_dashboard": {  # Web interface settings
            "refresh_rate": 1000,       # 1-second refresh rate
            "enable_gps": True,         # Enable GPS monitoring
            "enable_power": True,       # Enable power monitoring
            "enable_navigation": True   # Enable navigation monitoring
        }
    }

    # Save complete configuration to file
    with open(CONFIG_FILE, 'w') as f:
        json.dump(full_config, f, indent=2)
    print(f"\n✓ Complete config saved to {CONFIG_FILE}")

    # Step 6: Optionally create systemd service for auto-start
    create_service()
    
    # Step 7: Display setup summary and next steps
    print_summary()

if __name__ == "__main__":
    main()
