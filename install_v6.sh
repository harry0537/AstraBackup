#!/bin/bash
# Project Astra NZ - V6 Installation Script
# Quick setup for all dependencies and permissions

set -e  # Exit on error

echo "========================================================"
echo "PROJECT ASTRA NZ - V6 INSTALLATION"
echo "========================================================"
echo ""

# Check if running in correct directory
if [ ! -f "combo_proximity_bridge_v6.py" ]; then
    echo "✗ Error: Run this script from the v6 directory"
    echo "  cd ~/harry/AstraBackup/v6"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check Python version
echo "[1/5] Checking Python"
echo "----------------------------------------"
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✓ Python 3 installed: $PYTHON_VERSION"
else
    echo "✗ Python 3 not found"
    exit 1
fi

# Step 2: Create/activate virtual environment
echo ""
echo "[2/5] Virtual Environment"
echo "----------------------------------------"
VENV_PATH="$HOME/rover_venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment at $VENV_PATH"
    python3 -m venv "$VENV_PATH"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"
echo "✓ Virtual environment activated"

# Step 3: Install Python dependencies
echo ""
echo "[3/5] Python Dependencies"
echo "----------------------------------------"

# Upgrade pip first
pip install --upgrade pip -q

# Core dependencies
PACKAGES=(
    "rplidar-roboticia"
    "pymavlink"
    "pyrealsense2"
    "opencv-python"
    "numpy"
    "Pillow"
    "requests"
    "flask"
)

for pkg in "${PACKAGES[@]}"; do
    echo -n "Installing $pkg... "
    if pip install "$pkg" -q; then
        echo "✓"
    else
        echo "✗ (may already be installed)"
    fi
done

# Step 4: Permissions setup
echo ""
echo "[4/5] Device Permissions"
echo "----------------------------------------"

# Check dialout group
if groups | grep -q dialout; then
    echo "✓ User in dialout group"
else
    echo "⚠ Adding user to dialout group"
    sudo usermod -aG dialout "$USER"
    echo "  ⚠ You must logout and login for this to take effect!"
fi

# Set temporary permissions
if [ -e "/dev/ttyUSB0" ]; then
    sudo chmod 666 /dev/ttyUSB0
    echo "✓ RPLidar permissions set"
else
    echo "⚠ RPLidar not connected (/dev/ttyUSB0)"
fi

if [ -e "/dev/ttyACM0" ]; then
    sudo chmod 666 /dev/ttyACM0
    echo "✓ Pixhawk permissions set"
else
    echo "⚠ Pixhawk not found at /dev/ttyACM0"
fi

# Step 5: Hardware check
echo ""
echo "[5/5] Hardware Detection"
echo "----------------------------------------"

# RPLidar
if [ -e "/dev/ttyUSB0" ]; then
    echo "✓ RPLidar detected at /dev/ttyUSB0"
else
    echo "✗ RPLidar not found"
fi

# Pixhawk
PIXHAWK_FOUND=false
if [ -e "/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00" ]; then
    echo "✓ Pixhawk detected (by-id)"
    PIXHAWK_FOUND=true
elif [ -e "/dev/ttyACM0" ]; then
    echo "✓ Pixhawk detected at /dev/ttyACM0"
    PIXHAWK_FOUND=true
else
    echo "✗ Pixhawk not found"
fi

# RealSense
if lsusb | grep -q "8086"; then
    echo "✓ RealSense detected (Intel device)"
else
    echo "⚠ RealSense not detected (optional)"
fi

# Create config file
echo ""
echo "[Configuration]"
echo "----------------------------------------"
if [ ! -f "rover_config_v6.json" ]; then
    cat > rover_config_v6.json <<EOF
{
  "dashboard_ip": "10.244.77.186",
  "dashboard_port": 8081,
  "mavlink_port": 14550
}
EOF
    echo "✓ Config file created"
else
    echo "✓ Config file exists"
fi

# Create logs directory
mkdir -p logs
echo "✓ Logs directory ready"

# Summary
echo ""
echo "========================================================"
echo "INSTALLATION COMPLETE"
echo "========================================================"
echo ""
echo "Quick Start:"
echo "  1. Activate venv:  source ~/rover_venv/bin/activate"
echo "  2. Run manager:    python3 rover_manager_v6.py"
echo "  3. View dashboard: http://10.244.77.186:8081"
echo ""
echo "OR run components individually:"
echo "  python3 combo_proximity_bridge_v6.py  # Component 195"
echo "  python3 data_relay_v6.py              # Component 197"
echo "  python3 simple_crop_monitor_v6.py     # Component 198"
echo ""

if groups | grep -q dialout; then
    echo "✓ Ready to start!"
else
    echo "⚠ IMPORTANT: Logout and login to apply dialout group permissions"
fi
