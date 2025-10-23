#!/bin/bash
# Project Astra NZ - Virtual Environment Activation Script
# This script activates the rover virtual environment

VENV_PATH="$HOME/rover_venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Run: python3 rover_setup_v8.py"
    exit 1
fi

echo "🐍 Activating rover virtual environment..."
source "$VENV_PATH/bin/activate"

echo "✅ Virtual environment activated!"
echo "Python: $(which python3)"
echo "Pip: $(which pip)"

# Test critical imports
echo "🧪 Testing critical imports..."
python3 -c "
try:
    import rplidar
    print('✓ RPLidar OK')
except ImportError as e:
    print('✗ RPLidar Error:', e)

try:
    import pymavlink
    print('✓ MAVLink OK')
except ImportError as e:
    print('✗ MAVLink Error:', e)

try:
    import pyrealsense2
    print('✓ RealSense OK')
except ImportError as e:
    print('✗ RealSense Error:', e)

try:
    import flask
    print('✓ Flask OK')
except ImportError as e:
    print('✗ Flask Error:', e)
"

echo ""
echo "🚀 Ready to run rover components!"
echo "Run: python3 rover_manager_v8.py"