#!/bin/bash
# Start Obstacle-Based Navigation System
# This script starts the proximity bridge and navigation system

echo "============================================================"
echo "Starting Obstacle-Based Navigation System"
echo "============================================================"

# Check if we're in the right directory
if [ ! -f "combo_proximity_bridge_v9.py" ]; then
    echo "ERROR: Must run from v9 directory"
    echo "Run: cd /path/to/v9 && ./START_OBSTACLE_NAVIGATION.sh"
    exit 1
fi

# Check if proximity bridge is already running
if pgrep -f "combo_proximity_bridge_v9.py" > /dev/null; then
    echo "✓ Proximity bridge already running"
else
    echo "Starting proximity bridge..."
    python3 combo_proximity_bridge_v9.py &
    PROX_PID=$!
    echo "  Started with PID: $PROX_PID"
    echo "  Waiting 5 seconds for initialization..."
    sleep 5
fi

# Check if proximity data is available
if [ -f "/tmp/proximity_v9.json" ]; then
    echo "✓ Proximity data file exists"
else
    echo "⚠ Warning: Proximity data file not found"
    echo "  Waiting 10 more seconds..."
    sleep 10
    if [ ! -f "/tmp/proximity_v9.json" ]; then
        echo "✗ ERROR: Proximity bridge not providing data"
        echo "  Check proximity bridge output for errors"
        exit 1
    fi
fi

echo ""
echo "Starting obstacle navigation..."
echo "  Press Ctrl+C to stop"
echo "============================================================"
echo ""

# Start navigation (foreground so we can see output)
python3 obstacle_navigation_v9.py

