#!/bin/bash
#
# Project Astra NZ - V9 Stop Script
# Stops all V9 components cleanly
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================================================"
echo "PROJECT ASTRA NZ - V9 SHUTDOWN"
echo "======================================================================"
echo ""

echo -e "${YELLOW}Stopping all V9 components...${NC}"
echo ""

# Find and display V9 processes
echo "Active V9 processes:"
ps aux | grep -E "_v9.py" | grep -v grep | awk '{print "  • " $11 " (PID: " $2 ")"}'

# Stop all V9 processes
pkill -f "realsense_vision_server_v9.py"
pkill -f "combo_proximity_bridge_v9.py"
pkill -f "simple_crop_monitor_v9.py"
pkill -f "telemetry_dashboard_v9.py"
pkill -f "data_relay_v9.py"

# Wait a moment
sleep 2

# Check if anything is still running
if ps aux | grep -E "_v9.py" | grep -v grep > /dev/null; then
    echo -e "${YELLOW}⚠ Some processes still running, forcing shutdown...${NC}"
    pkill -9 -f "_v9.py"
    sleep 1
fi

# Verify all stopped
if ps aux | grep -E "_v9.py" | grep -v grep > /dev/null; then
    echo -e "${RED}✗ Failed to stop some processes${NC}"
    echo "Remaining processes:"
    ps aux | grep -E "_v9.py" | grep -v grep
    exit 1
else
    echo -e "${GREEN}✓ All V9 components stopped${NC}"
fi

echo ""
echo "To restart V9:"
echo "  ./start_rover_v9.sh"
echo ""
echo "To start V8 instead:"
echo "  cd ../v8 && python3 rover_manager_v8.py"
echo ""

exit 0

