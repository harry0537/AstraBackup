#!/usr/bin/env python3
"""
Project Astra NZ - Rover Setup Script v2.10
Automated setup and installation for the autonomous rover system
"""

import os
import sys
import subprocess
import json

def print_step(step_num, description):
    """Print a formatted step message"""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {description}")
    print(f"{'='*60}\n")

def check_python_version():
    """Check if Python 3.8+ is available"""
    print_step(1, "Checking Python Version")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ ERROR: Python 3.8 or higher is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def install_system_dependencies():
    """Install system-level dependencies"""
    print_step(2, "Installing System Dependencies")
    print("This may require sudo/administrator privileges...")
    
    commands = [
        ["apt", "update"],
        ["apt", "install", "-y", "python3-dev", "python3-pip", "python3-venv", "build-essential"]
    ]
    
    try:
        for cmd in commands:
            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(["sudo"] + cmd, check=False, capture_output=True)
            if result.returncode != 0:
                print(f"⚠️  Warning: Command failed (may need manual installation)")
    except FileNotFoundError:
        print("⚠️  Skipping system dependencies (apt not found - may be Windows/Mac)")
    
    print("✅ System dependencies check complete")

def create_virtual_environment():
    """Create Python virtual environment"""
    print_step(3, "Creating Virtual Environment")
    venv_path = os.path.expanduser("~/rover_venv")
    
    if os.path.exists(venv_path):
        print(f"⚠️  Virtual environment already exists at {venv_path}")
        response = input("   Recreate? (y/N): ").strip().lower()
        if response == 'y':
            import shutil
            shutil.rmtree(venv_path)
            print("   Removed existing virtual environment")
        else:
            print("✅ Using existing virtual environment")
            return venv_path
    
    print(f"Creating virtual environment at {venv_path}...")
    subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
    print("✅ Virtual environment created")
    return venv_path

def install_python_dependencies(venv_path):
    """Install Python dependencies"""
    print_step(4, "Installing Python Dependencies")
    
    pip_path = os.path.join(venv_path, "bin", "pip")
    if sys.platform == "win32":
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe")
    
    if not os.path.exists(pip_path):
        print("❌ ERROR: pip not found in virtual environment")
        return False
    
    print("Installing packages from requirements.txt...")
    result = subprocess.run(
        [pip_path, "install", "--upgrade", "pip"],
        check=False
    )
    
    result = subprocess.run(
        [pip_path, "install", "-r", "requirements.txt"],
        check=False
    )
    
    if result.returncode == 0:
        print("✅ Python dependencies installed")
        return True
    else:
        print("⚠️  Some packages may have failed to install")
        print("   You may need to install them manually")
        return True  # Continue anyway

def create_config_file():
    """Create default configuration file if it doesn't exist"""
    print_step(5, "Creating Configuration File")
    
    config_file = "rover_config.json"
    
    if os.path.exists(config_file):
        print(f"✅ Configuration file already exists: {config_file}")
        return True
    
    default_config = {
        "dashboard_ip": "0.0.0.0",
        "dashboard_port": 8081,
        "mavlink_port": 14550,
        "lidar_port": "/dev/ttyUSB0",
        "pixhawk_port": "/dev/ttyACM0"
    }
    
    print(f"Creating default configuration: {config_file}")
    with open(config_file, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    print("✅ Configuration file created")
    print("⚠️  Please edit rover_config.json to match your hardware setup")
    return True

def check_permissions():
    """Check and guide user on permissions"""
    print_step(6, "Checking Permissions")
    
    print("For serial port access (LiDAR, Pixhawk), you may need to:")
    print("  1. Add your user to the 'dialout' group:")
    print("     sudo usermod -aG dialout $USER")
    print("  2. Log out and log back in for changes to take effect")
    print("  3. Check permissions: ls -l /dev/ttyUSB* /dev/ttyACM*")
    
    print("\n✅ Permission check complete")
    return True

def print_summary(venv_path):
    """Print setup summary and next steps"""
    print_step(7, "Setup Complete!")
    
    python_cmd = os.path.join(venv_path, "bin", "python3")
    if sys.platform == "win32":
        python_cmd = os.path.join(venv_path, "Scripts", "python.exe")
    
    print("✅ Setup completed successfully!")
    print("\n📋 Next Steps:")
    print("   1. Edit rover_config.json to match your hardware")
    print("   2. Connect your hardware (Pixhawk, LiDAR, RealSense)")
    print("   3. Run: python3 rover_manager.py")
    print(f"      (or: {python_cmd} rover_manager.py)")
    print("\n🌐 Dashboard will be available at:")
    print("   http://localhost:8081")
    print("   Username: admin")
    print("   Password: admin")
    print("\n📖 For more information, see README.md")

def main():
    """Main setup function"""
    print("="*60)
    print("Project Astra NZ - Rover Setup v2.10")
    print("="*60)
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Run setup steps
    if not check_python_version():
        sys.exit(1)
    
    install_system_dependencies()
    venv_path = create_virtual_environment()
    
    if not install_python_dependencies(venv_path):
        print("⚠️  Setup completed with warnings")
        print("   You may need to install dependencies manually")
    
    create_config_file()
    check_permissions()
    print_summary(venv_path)

if __name__ == "__main__":
    main()

