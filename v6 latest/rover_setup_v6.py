#!/usr/bin/env python3
"""
Project Astra NZ - Rover Setup V6
Streamlined setup for rover system
"""

import os
import sys
import subprocess
import json
import socket

CONFIG_FILE = "rover_config_v6.json"

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
        'flask': 'flask'
    }
    
    venv_pip = os.path.expanduser("~/rover_venv/bin/pip")
    
    if not os.path.exists(os.path.expanduser("~/rover_venv")):
        print("Creating virtual environment...")
        run_cmd(f"python3 -m venv {os.path.expanduser('~/rover_venv')}")
    
    for pkg, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"  ✓ {pkg}")
        except ImportError:
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
    
    if check_sudo() and not os.path.exists(rules_file):
        print("Creating udev rules...")
        with open(rules_file, 'w') as f:
            f.write(rules)
        run_cmd("udevadm control --reload-rules")
        run_cmd("udevadm trigger")
        print("✓ Device rules created")
    elif not os.path.exists(rules_file):
        print("⚠ Udev rules need sudo")
        print("  Run: sudo python3 rover_setup_v6.py")
    else:
        print("✓ Device rules exist")

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
    
    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✓ Config saved to {CONFIG_FILE}")
    
    return config

def test_hardware():
    """Test hardware connections"""
    print("\n[4/4] Hardware Test")
    print("-" * 40)
    
    # LiDAR
    if any(os.path.exists(p) for p in ['/dev/rplidar', '/dev/ttyUSB0']):
        print("✓ RPLidar detected")
    else:
        print("⚠ RPLidar not found")
    
    # Pixhawk
    if any(os.path.exists(p) for p in ['/dev/pixhawk', '/dev/ttyACM0']):
        print("✓ Pixhawk detected")
    else:
        print("⚠ Pixhawk not found")
    
    # RealSense
    try:
        import pyrealsense2
        print("✓ RealSense library available")
    except:
        print("⚠ RealSense library not found")

def create_service():
    """Optionally create systemd service"""
    print("\n[Optional] Auto-Start Service")
    print("-" * 40)
    
    response = input("Enable auto-start on boot? [y/N]: ")
    if response.lower() == 'y':
        if not check_sudo():
            print("⚠ Need sudo to create service")
            print("  Run: sudo python3 rover_setup_v6.py")
            return
        
        service = f"""[Unit]
Description=Project Astra NZ Rover
After=network.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
WorkingDirectory={os.getcwd()}
Environment="PATH={os.path.expanduser('~/rover_venv/bin')}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart={os.path.expanduser('~/rover_venv/bin/python3')} {os.getcwd()}/rover_manager_v6.py --auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        with open('/etc/systemd/system/astra-rover.service', 'w') as f:
            f.write(service)
        run_cmd("systemctl daemon-reload")
        run_cmd("systemctl enable astra-rover.service")
        print("✓ Auto-start enabled")
        print("  Start: sudo systemctl start astra-rover")
        print("  Stop:  sudo systemctl stop astra-rover")

def print_summary():
    """Print setup summary"""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        print(f"\nDashboard: {config['dashboard_ip']}:{config['dashboard_port']}")
        print(f"MAVLink:   Port {config['mavlink_port']}")
    
    print("\nNext Steps:")
    print("1. Run: python3 rover_manager_v6.py")
    print("2. View: http://10.244.77.186:8081")
    print("\n✓ Ready to start!")

def main():
    """Main execution"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - ROVER SETUP V6")
    print("=" * 60)
    
    install_dependencies()
    setup_permissions()
    configure_network()
    test_hardware()
    create_service()
    print_summary()

if __name__ == "__main__":
    main()
