#!/bin/bash
#
# Project Astra NZ - V9 Startup Script
# Starts all components in correct order
#

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "PROJECT ASTRA NZ - V9 STARTUP"
echo "======================================================================"
echo ""

# Check if running from correct directory
if [ ! -f "realsense_vision_server_v9.py" ]; then
    echo -e "${RED}ERROR: Script must be run from v9 directory${NC}"
    echo "Run: cd /path/to/v9 && ./start_rover_v9.sh"
    exit 1
fi

# Check Python environment
if [ ! -d "$HOME/rover_venv" ]; then
    echo -e "${YELLOW}WARNING: Virtual environment not found at ~/rover_venv${NC}"
    echo "Using system Python..."
    PYTHON_CMD="python3"
else
    echo -e "${GREEN}✓ Using virtual environment${NC}"
    PYTHON_CMD="$HOME/rover_venv/bin/python3"
fi

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null
    return $?
}

# Function to start component
start_component() {
    local script=$1
    local name=$2
    local wait_time=$3
    
    echo -e "\n${YELLOW}Starting ${name}...${NC}"
    
    if is_running "$script"; then
        echo -e "${YELLOW}⚠ ${name} is already running${NC}"
        return 0
    fi
    
    $PYTHON_CMD "$script" &
    local pid=$!
    
    # Wait a bit and check if it's still running
    sleep 2
    if ps -p $pid > /dev/null; then
        echo -e "${GREEN}✓ ${name} started (PID: $pid)${NC}"
        if [ $wait_time -gt 0 ]; then
            echo "  Waiting ${wait_time} seconds for initialization..."
            sleep $wait_time
        fi
        return 0
    else
        echo -e "${RED}✗ ${name} failed to start${NC}"
        return 1
    fi
}

# Stop function for cleanup
stop_all() {
    echo -e "\n${YELLOW}Stopping all V9 components...${NC}"
    pkill -f "_v9.py"
    sleep 2
    echo -e "${GREEN}✓ All components stopped${NC}"
}

# Trap for cleanup on exit
trap stop_all EXIT INT TERM

# Create necessary directories
echo -e "${YELLOW}Setting up directories...${NC}"
mkdir -p /tmp/vision_v9
mkdir -p /tmp/crop_archive
mkdir -p /tmp/rover_vision
echo -e "${GREEN}✓ Directories ready${NC}"

# Check if V9 is already running
if is_running "realsense_vision_server_v9.py"; then
    echo -e "\n${YELLOW}======================================${NC}"
    echo -e "${YELLOW}V9 components are already running!${NC}"
    echo -e "${YELLOW}======================================${NC}"
    echo ""
    echo "To stop and restart:"
    echo "  pkill -f _v9.py"
    echo "  ./start_rover_v9.sh"
    echo ""
    echo "To view status:"
    echo "  ./check_v9_health.sh"
    exit 0
fi

# ===================================================================
# COMPONENT STARTUP SEQUENCE (CRITICAL ORDER!)
# ===================================================================

echo -e "\n${GREEN}======================================================================"
echo "STARTING V9 COMPONENTS (in correct order)"
echo "======================================================================${NC}"

# 1. Vision Server (MUST START FIRST - owns camera)
if ! start_component "realsense_vision_server_v9.py" "Vision Server (Component 196)" 5; then
    echo -e "${RED}CRITICAL: Vision Server failed to start${NC}"
    echo "Cannot continue without Vision Server"
    exit 1
fi

# Verify Vision Server is ready
echo "Verifying Vision Server is operational..."
for i in {1..10}; do
    if [ -f "/tmp/vision_v9/status.json" ]; then
        status=$(cat /tmp/vision_v9/status.json | grep -o '"status":"RUNNING"')
        if [ ! -z "$status" ]; then
            echo -e "${GREEN}✓ Vision Server is operational${NC}"
            break
        fi
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}✗ Vision Server not responding after 10 seconds${NC}"
        exit 1
    fi
    sleep 1
done

# 2. Proximity Bridge (reads depth from Vision Server)
start_component "combo_proximity_bridge_v9.py" "Proximity Bridge (Component 195)" 2

# 3. Crop Monitor (reads RGB from Vision Server)
start_component "simple_crop_monitor_v9.py" "Crop Monitor (Component 198)" 2

# 4. Telemetry Dashboard
start_component "telemetry_dashboard_v9.py" "Telemetry Dashboard (Component 194)" 2

# 5. Data Relay
start_component "data_relay_v9.py" "Data Relay (Component 197)" 0

# ===================================================================
# STARTUP COMPLETE
# ===================================================================

echo -e "\n${GREEN}======================================================================"
echo "V9 STARTUP COMPLETE"
echo "======================================================================${NC}"
echo ""
echo "Active Components:"
ps aux | grep -E "realsense_vision_server_v9|combo_proximity_bridge_v9|simple_crop_monitor_v9|telemetry_dashboard_v9|data_relay_v9" | grep -v grep | awk '{print "  • " $11 " (PID: " $2 ")"}'
echo ""
echo "Access Points:"
echo "  • Dashboard: http://10.244.77.186:8081"
echo "  • Local: http://localhost:8081"
echo ""
echo "Monitoring:"
echo "  • Health Check: ./check_v9_health.sh"
echo "  • View Logs: tail -f /tmp/vision_v9/vision_server.log"
echo "  • Status Files: ls -lh /tmp/vision_v9/"
echo ""
echo "Emergency Stop:"
echo "  • Press Ctrl+C or run: pkill -f _v9.py"
echo ""
echo -e "${YELLOW}All components will stop when this script exits.${NC}"
echo "Press Ctrl+C to stop all components..."
echo ""

# Keep script running
while true; do
    sleep 5
    # Check if critical components are still running
    if ! is_running "realsense_vision_server_v9.py"; then
        echo -e "\n${RED}✗ CRITICAL: Vision Server stopped unexpectedly!${NC}"
        stop_all
        exit 1
    fi
done

