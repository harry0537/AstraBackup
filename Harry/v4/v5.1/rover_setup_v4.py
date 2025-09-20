#!/usr/bin/env python3
"""
Project Astra NZ - Rover Setup V4
Configures system, installs dependencies, sets IP addresses
"""

import os
import sys
import subprocess
import json
import socket

# Configuration file path
CONFIG_FILE = "rover_config_v4.json"

def run_command(cmd, check=True):
    """Run shell command"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_root():
    """Check if running as root when needed"""
    if os.geteuid() == 0:
        print("⚠️  Running as root - only for system changes")
    return os.geteuid() == 0

def install_system_dependencies():
    """Install system-level dependencies"""
    print("\n[1/7] System Dependencies")
    print("-" * 40)
    
    packages = [
        "python3-pip",
        "python3-dev",
        "python3-venv",
        "git",
        "build-essential",
        "cmake",
        "libusb-1.0-0-dev",
        "libudev-dev"
    ]
    
    print("Checking system packages...")
    missing = []
    
    for pkg in packages:
        success, out, _ = run_command(f"dpkg -l | grep -w {pkg}", check=False)
        if not success or pkg not in out:
            missing.append(pkg)
            
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        if not check_root():
            print("❌ Need sudo privileges to install packages")
            print(f"Run: sudo apt-get install {' '.join(missing)}")
            return False
        
        run_command("apt-get update")
        for pkg in missing:
            print(f"  Installing {pkg}...")
            success, _, _ = run_command(f"apt-get install -y {pkg}")
            if success:
                print(f"  ✓ {pkg} installed")
            else:
                print(f"  ✗ Failed to install {pkg}")
                
    print("✓ System dependencies ready")
    return True

def setup_python_environment():
    """Setup Python virtual environment"""
    print("\n[2/7] Python Environment")
    print("-" * 40)
    
    venv_path = os.path.expanduser("~/rover_venv")
    
    if not os.path.exists(venv_path):
        print("Creating virtual environment...")
        success, _, _ = run_command(f"python3 -m venv {venv_path}")
        if success:
            print(f"✓ Virtual environment created at {venv_path}")
        else:
            print("✗ Failed to create virtual environment")
            return False
    else:
        print(f"✓ Virtual environment exists at {venv_path}")
        
    # Install Python packages
    pip_cmd = f"{venv_path}/bin/pip"
    
    packages = {
        "rplidar-roboticia": "RPLidar",
        "pymavlink": "MAVLink",
        "pyrealsense2": "RealSense",
        "opencv-python": "OpenCV",
        "numpy": "NumPy",
        "Pillow": "Image processing",
        "requests": "HTTP client",
        "flask": "Web framework"
    }
    
    print("\nInstalling Python packages...")
    for pkg, name in packages.items():
        print(f"  Installing {name}...", end='')
        success, _, _ = run_command(f"{pip_cmd} install {pkg}", check=False)
        if success:
            print(" ✓")
        else:
            print(" ✗")
            
    print("✓ Python environment configured")
    return True

def configure_permissions():
    """Configure device permissions"""
    print("\n[3/7] Device Permissions")
    print("-" * 40)
    
    user = os.environ.get('USER', 'pi')
    
    # Check dialout group
    success, groups, _ = run_command(f"groups {user}")
    if 'dialout' not in groups:
        print(f"Adding {user} to dialout group...")
        if check_root():
            run_command(f"usermod -aG dialout {user}")
            print(f"✓ Added {user} to dialout group")
            print("⚠️  Logout and login for changes to take effect")
        else:
            print(f"⚠️  User not in dialout group")
            print(f"Run: sudo usermod -aG dialout {user}")
    else:
        print(f"✓ User {user} in dialout group")
        
    # Create udev rules
    rules_file = "/etc/udev/rules.d/99-astra.rules"
    rules_content = """# Project Astra NZ Device Rules
# RPLidar
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"
# Pixhawk
SUBSYSTEM=="tty", ATTRS{idVendor}=="2dae", MODE="0666", SYMLINK+="pixhawk"
# RealSense
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", MODE="0666"
"""
    
    if not os.path.exists(rules_file):
        print("Creating udev rules...")
        if check_root():
            with open(rules_file, 'w') as f:
                f.write(rules_content)
            run_command("udevadm control --reload-rules")
            run_command("udevadm trigger")
            print("✓ Device rules created")
        else:
            print("⚠️  Cannot create udev rules without sudo")
            print("Device permissions may require manual setup")
    else:
        print("✓ Device rules exist")
        
    return True

def setup_network():
    """Configure network settings"""
    print("\n[4/7] Network Configuration")
    print("-" * 40)
    
    # Check ZeroTier
    success, _, _ = run_command("which zerotier-cli", check=False)
    if not success:
        print("⚠️  ZeroTier not installed")
        print("Install from: https://www.zerotier.com/download/")
    else:
        # Check ZeroTier status
        success, status, _ = run_command("zerotier-cli status")
        if success and "ONLINE" in status:
            print("✓ ZeroTier online")
            
            # Join network
            network_id = "41d49af6c276269e"
            success, networks, _ = run_command("zerotier-cli listnetworks")
            if network_id not in networks:
                print(f"Joining ZeroTier network {network_id}...")
                if check_root():
                    run_command(f"zerotier-cli join {network_id}")
                    print("✓ Joined UGV Network")
                else:
                    print(f"Run: sudo zerotier-cli join {network_id}")
            else:
                print("✓ Connected to UGV Network")
        else:
            print("⚠️  ZeroTier not running")
            print("Run: sudo systemctl start zerotier-one")
            
    return True

def configure_ip_addresses():
    """Configure IP addresses to avoid conflicts"""
    print("\n[5/7] IP Address Configuration")
    print("-" * 40)
    
    config = {
        "rover_ip": "localhost",
        "dashboard_ip": "10.244.77.186",
        "dashboard_port": 8081,
        "mavlink_port": 14550,
        "mavproxy_port": 14551,
        "web_port": 5000,
        "component_base_port": 15000
    }
    
    # Detect local IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        config["rover_ip"] = local_ip
        print(f"✓ Rover IP: {local_ip}")
    except:
        print("⚠️  Could not detect local IP")
        
    # Check port availability
    ports_to_check = [
        ("MAVLink", 14550),
        ("MAVProxy", 14551),
        ("Web Interface", 5000),
        ("Component Base", 15000)
    ]
    
    for name, port in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            print(f"⚠️  Port {port} ({name}) already in use")
            # Find alternative
            for alt_port in range(port + 1, port + 100):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', alt_port))
                sock.close()
                if result != 0:
                    print(f"  Using alternative port {alt_port}")
                    if "mavlink" in name.lower():
                        config["mavlink_port"] = alt_port
                    elif "mavproxy" in name.lower():
                        config["mavproxy_port"] = alt_port
                    elif "web" in name.lower():
                        config["web_port"] = alt_port
                    elif "component" in name.lower():
                        config["component_base_port"] = alt_port
                    break
        else:
            print(f"✓ Port {port} ({name}) available")
            
    # Save configuration
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\n✓ Configuration saved to {CONFIG_FILE}")
    
    return config

def create_systemd_service():
    """Create systemd service for auto-start"""
    print("\n[6/7] Auto-Start Service")
    print("-" * 40)
    
    service_file = "/etc/systemd/system/astra-rover.service"
    service_content = f"""[Unit]
Description=Project Astra NZ Rover System
After=network.target

[Service]
Type=simple
User={os.environ.get('USER', 'pi')}
WorkingDirectory={os.getcwd()}
Environment="PATH=/home/{os.environ.get('USER', 'pi')}/rover_venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/{os.environ.get('USER', 'pi')}/rover_venv/bin/python3 {os.getcwd()}/rover_manager_v4.py --auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    response = input("Enable auto-start on boot? [y/N]: ")
    if response.lower() == 'y':
        if check_root():
            with open(service_file, 'w') as f:
                f.write(service_content)
            run_command("systemctl daemon-reload")
            run_command("systemctl enable astra-rover.service")
            print("✓ Auto-start service created")
            print("  Start: sudo systemctl start astra-rover")
            print("  Stop:  sudo systemctl stop astra-rover")
            print("  Logs:  sudo journalctl -u astra-rover -f")
        else:
            print("⚠️  Need sudo to create service")
            print("Run setup as: sudo python3 rover_setup_v4.py")
    else:
        print("⚠️  Auto-start not configured")
        
    return True

def test_connections():
    """Test hardware and network connections"""
    print("\n[7/7] Connection Tests")
    print("-" * 40)
    
    # Test RPLidar
    if os.path.exists('/dev/ttyUSB0'):
        print("✓ RPLidar device present")
    else:
        print("⚠️  RPLidar not detected")
        
    # Test Pixhawk
    pixhawk_found = False
    for device in os.listdir('/dev/'):
        if 'ttyACM' in device or 'Pixhawk' in device:
            pixhawk_found = True
            break
    if pixhawk_found:
        print("✓ Pixhawk device present")
    else:
        print("⚠️  Pixhawk not detected")
        
    # Test dashboard connection
    dashboard_ip = "10.244.77.186"
    success, _, _ = run_command(f"ping -c 1 -W 2 {dashboard_ip}", check=False)
    if success:
        print(f"✓ Dashboard reachable at {dashboard_ip}")
    else:
        print(f"⚠️  Dashboard not reachable at {dashboard_ip}")
        print("  Check ZeroTier connection")
        
    return True

def print_summary():
    """Print setup summary"""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        print("\nConfiguration:")
        print(f"  Rover IP:       {config.get('rover_ip', 'Unknown')}")
        print(f"  Dashboard:      {config['dashboard_ip']}:{config['dashboard_port']}")
        print(f"  MAVLink Port:   {config['mavlink_port']}")
        print(f"  Web Interface:  {config['web_port']}")
        
    print("\nNext Steps:")
    print("1. Run hardware check: python3 hardware_check_v4.py")
    print("2. Start rover system: python3 rover_manager_v4.py")
    print("3. Access dashboard:   http://10.244.77.186:8081")
    
    print("\n✅ Setup complete!")

def main():
    """Main setup execution"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - ROVER SETUP V4")
    print("=" * 60)
    
    # Check if need sudo for some operations
    if '--system' in sys.argv and not check_root():
        print("❌ System setup requires sudo")
        print("Run: sudo python3 rover_setup_v4.py --system")
        return False
        
    # Run setup steps
    if '--system' in sys.argv:
        install_system_dependencies()
        
    setup_python_environment()
    configure_permissions()
    setup_network()
    config = configure_ip_addresses()
    
    if '--service' in sys.argv:
        create_systemd_service()
        
    test_connections()
    print_summary()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)