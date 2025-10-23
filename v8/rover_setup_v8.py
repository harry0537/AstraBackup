#!/usr/bin/env python3
"""
Project Astra NZ - Rover Setup V8
Streamlined setup for rover system - Bug Fixes from V7
"""

import os
import sys
import subprocess
import json
import socket
import glob
import time

CONFIG_FILE = "rover_config_v8.json"

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
    """Install Python dependencies"""
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

    if not os.path.exists(venv_path):
        print("Creating virtual environment...")
        if not run_cmd(f"python3 -m venv {venv_path}"):
            print("✗ Failed to create virtual environment")
            return False
        print("✓ Virtual environment created")

    # FIX BUG #2: Check packages in venv, not current environment
    for pkg, import_name in packages.items():
        try:
            # Test if package exists in venv by trying to import it
            result = subprocess.run(
                [venv_python, "-c", f"import {import_name}"],
                capture_output=True,
                timeout=5
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

    print("✓ Dependencies ready")

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

    # Create udev rules
    rules_file = "/etc/udev/rules.d/99-astra.rules"
    rules = """# Project Astra NZ
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2dae", MODE="0666", SYMLINK+="pixhawk"
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", MODE="0666"
"""

    # FIX BUG #12: Better permission message handling
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
        print("  Run: sudo python3 rover_setup_v8.py")

def configure_network():
    """Configure network settings"""
    print("\n[3/4] Network")
    print("-" * 40)

    config = {
        "dashboard_ip": "10.244.77.186",
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
                               config['dashboard_ip']],
                              capture_output=True, timeout=3)
        if result.returncode == 0:
            print(f"✓ Dashboard reachable at {config['dashboard_ip']}")
        else:
            print(f"⚠ Dashboard not reachable")
    except:
        print("⚠ Cannot ping dashboard")

    return config

def detect_hardware():
    """Auto-detect all hardware and return addresses"""
    print("\n[4/4] Hardware Detection")
    print("-" * 40)

    hardware = {
        'lidar_port': None,
        'pixhawk_port': None,
        'realsense_available': False,
        'realsense_config': None
    }

    # Virtual environment Python path
    venv_path = os.path.expanduser("~/rover_venv")
    venv_python = os.path.join(venv_path, "bin", "python3")
    
    # Detect LIDAR
    print("Detecting RPLidar...")
    
    # First, scan for all available USB ports
    usb_ports = []
    for i in range(10):  # Check up to 10 USB ports
        port = f'/dev/ttyUSB{i}'
        if os.path.exists(port):
            usb_ports.append(port)
    
    lidar_candidates = [
        '/dev/rplidar',  # Symlink from udev rules
    ] + usb_ports + [
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3'
    ]

    for port in lidar_candidates:
        if os.path.exists(port):
            test_lidar = None
            try:
                # Quick test to verify it's a LIDAR using venv Python
                result = subprocess.run(
                    [venv_python, "-c", f"""
import sys
from rplidar import RPLidar
test_lidar = RPLidar('{port}')
info = test_lidar.get_info()
test_lidar.disconnect()
print(f"LIDAR_DETECTED:{port}:{{info['model']}}")
"""],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=15
                )
                if result.returncode == 0:
                    output = result.stdout.decode().strip()
                    if "LIDAR_DETECTED:" in output:
                        port_info = output.split("LIDAR_DETECTED:")[1]
                        port_detected, model = port_info.split(":", 1)
                        hardware['lidar_port'] = port_detected
                        print(f"✓ RPLidar detected at {port_detected} (Model: {model})")
                        break
                else:
                    # Show error for USB ports
                    if '/dev/ttyUSB' in port:
                        error_output = result.stdout.decode().strip()
                        print(f"  Testing {port}: {error_output[:200]}")
            except Exception as e:
                # Show error for USB ports
                if '/dev/ttyUSB' in port:
                    print(f"  Testing {port}: {str(e)[:200]}")
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
            # Handle glob patterns
            matches = glob.glob(pattern)
            for port in matches:
                if os.path.exists(port):
                    test_conn = None
                    try:
                        # Quick test to verify it's a Pixhawk
                        from pymavlink import mavutil
                        test_conn = mavutil.mavlink_connection(port, baud=57600, timeout=2)
                        test_conn.wait_heartbeat(timeout=2)
                        test_conn.close()
                        hardware['pixhawk_port'] = port
                        print(f"✓ Pixhawk detected at {port}")
                        break
                    except Exception as e:
                        # FIX BUG #5: Always close connection on exception
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
                    # FIX BUG #5: Always close connection on exception
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
            (rs.stream.depth, 424, 240, rs.format.z16, 15),
            (rs.stream.depth, 320, 240, rs.format.z16, 15),
            (rs.stream.depth, 640, 480, rs.format.z16, 6),
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

                # FIX BUG #6: Always stop pipeline
                if pipeline:
                    try:
                        pipeline.stop()
                    except:
                        pass
                    pipeline = None

                # If we found a working config, exit the loop
                if hardware['realsense_config']:
                    break

            except Exception as e:
                # FIX BUG #6: Always stop pipeline on exception
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

def test_hardware():
    """Test hardware connections (legacy function)"""
    hardware = detect_hardware()

    # Print summary
    if hardware['lidar_port']:
        print("✓ RPLidar detected")
    else:
        print("⚠ RPLidar not found")

    if hardware['pixhawk_port']:
        print("✓ Pixhawk detected")
    else:
        print("⚠ Pixhawk not found")

    if hardware['realsense_available']:
        print("✓ RealSense library available")
    else:
        print("⚠ RealSense library not found")

    return hardware

def create_service():
    """Optionally create systemd service"""
    print("\n[Optional] Auto-Start Service")
    print("-" * 40)

    response = input("Enable auto-start on boot? [y/N]: ")
    if response.lower() == 'y':
        if not check_sudo():
            print("⚠ Need sudo to create service")
            print("  Run: sudo python3 rover_setup_v8.py")
            return

        service = f"""[Unit]
Description=Project Astra NZ Rover V8
After=network.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
WorkingDirectory={os.getcwd()}
Environment="PATH={os.path.expanduser('~/rover_venv/bin')}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart={os.path.expanduser('~/rover_venv/bin/python3')} {os.getcwd()}/rover_manager_v8.py --auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        with open('/etc/systemd/system/astra-rover-v8.service', 'w') as f:
            f.write(service)
        run_cmd("systemctl daemon-reload")
        run_cmd("systemctl enable astra-rover-v8.service")
        print("✓ Auto-start enabled")
        print("  Start: sudo systemctl start astra-rover-v8")
        print("  Stop:  sudo systemctl stop astra-rover-v8")

def verify_virtual_environment():
    """Verify virtual environment is working correctly"""
    print("\n[5/5] Virtual Environment Verification")
    print("-" * 40)
    
    venv_path = os.path.expanduser("~/rover_venv")
    venv_python = os.path.join(venv_path, "bin", "python3")
    
    if not os.path.exists(venv_python):
        print("✗ Virtual environment Python not found")
        return False
    
    # Test critical imports
    critical_imports = ['rplidar', 'pymavlink', 'pyrealsense2', 'flask']
    all_good = True
    
    for module in critical_imports:
        try:
            result = subprocess.run(
                [venv_python, "-c", f"import {module}"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✓ {module}")
            else:
                print(f"✗ {module} - Import failed")
                all_good = False
        except Exception as e:
            print(f"✗ {module} - Error: {e}")
            all_good = False
    
    if all_good:
        print("✓ Virtual environment ready")
    else:
        print("⚠ Virtual environment has issues")
    
    return all_good

def print_summary():
    """Print setup summary"""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE - V8")
    print("=" * 60)

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        print(f"\nDashboard: {config['dashboard_ip']}:{config['dashboard_port']}")
        print(f"MAVLink:   Port {config['mavlink_port']}")

    print("\nNext Steps:")
    print("1. Run: python3 rover_manager_v8.py")
    print("2. View: http://10.244.77.186:8081")
    print("\n✓ Ready to start!")

def main():
    """Main execution"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - ROVER SETUP V8")
    print("=" * 60)

    install_dependencies()
    setup_permissions()
    network_config = configure_network()
    hardware_config = detect_hardware()

    # Merge all configurations
    full_config = {**network_config, **hardware_config}

    # Save complete configuration
    with open(CONFIG_FILE, 'w') as f:
        json.dump(full_config, f, indent=2)
    print(f"\n✓ Complete config saved to {CONFIG_FILE}")

    create_service()
    verify_virtual_environment()
    print_summary()

if __name__ == "__main__":
    main()
