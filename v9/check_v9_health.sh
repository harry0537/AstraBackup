#!/bin/bash
#
# Project Astra NZ - V9 Health Check Script
# Checks status of all V9 components
#

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "PROJECT ASTRA NZ - V9 HEALTH CHECK"
echo "======================================================================"
echo ""

# Function to check if process is running
check_process() {
    local name=$1
    local script=$2
    
    if pgrep -f "$script" > /dev/null; then
        local pid=$(pgrep -f "$script")
        echo -e "${GREEN}✓ $name: RUNNING (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}✗ $name: STOPPED${NC}"
        return 1
    fi
}

# Function to check file age
check_file_age() {
    local file=$1
    local name=$2
    local max_age=$3
    
    if [ -f "$file" ]; then
        local age=$(($(date +%s) - $(stat -c %Y "$file")))
        if [ $age -lt $max_age ]; then
            echo -e "${GREEN}✓ $name: Fresh (${age}s old)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ $name: Stale (${age}s old, max ${max_age}s)${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ $name: Missing${NC}"
        return 1
    fi
}

# Check Processes
echo -e "${BLUE}=== Process Status ===${NC}"
check_process "Vision Server" "realsense_vision_server_v9.py"
vs_running=$?
check_process "Proximity Bridge" "combo_proximity_bridge_v9.py"
prox_running=$?
check_process "Crop Monitor" "simple_crop_monitor_v9.py"
crop_running=$?
check_process "Dashboard" "telemetry_dashboard_v9.py"
dash_running=$?
check_process "Data Relay" "data_relay_v9.py"
relay_running=$?

echo ""

# Check Vision Server Files
echo -e "${BLUE}=== Vision Server Status ===${NC}"
if [ -f "/tmp/vision_v9/status.json" ]; then
    echo "Vision Server Status:"
    cat /tmp/vision_v9/status.json | python3 -m json.tool 2>/dev/null | grep -E "status|uptime|fps|errors" || cat /tmp/vision_v9/status.json
    echo ""
fi

check_file_age "/tmp/vision_v9/rgb_latest.jpg" "RGB Frame" 2
check_file_age "/tmp/vision_v9/depth_latest.bin" "Depth Frame" 2
check_file_age "/tmp/vision_v9/rgb_latest.json" "RGB Metadata" 2
check_file_age "/tmp/vision_v9/depth_latest.json" "Depth Metadata" 2

echo ""

# Check Proximity Data
echo -e "${BLUE}=== Proximity Status ===${NC}"
if [ -f "/tmp/proximity_v9.json" ]; then
    check_file_age "/tmp/proximity_v9.json" "Proximity Data" 5
    echo "Min Distance:"
    cat /tmp/proximity_v9.json | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  {d.get('min_cm', 0)/100:.1f}m\")" 2>/dev/null || echo "  Parse error"
else
    echo -e "${RED}✗ Proximity Data: Missing${NC}"
fi

echo ""

# Check Crop Monitor
echo -e "${BLUE}=== Crop Monitor Status ===${NC}"
if [ -f "/tmp/crop_monitor_v9.json" ]; then
    check_file_age "/tmp/crop_monitor_v9.json" "Crop Monitor Status" 15
    echo "Archive Info:"
    cat /tmp/crop_monitor_v9.json | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"  Captures: {d.get('capture_count', 0)}\\n  Archived: {d.get('total_archived', 0)}\")" 2>/dev/null || echo "  Parse error"
else
    echo -e "${YELLOW}⚠ Crop Monitor Status: Missing${NC}"
fi

# Check archive
archive_count=$(ls /tmp/crop_archive/crop_*.jpg 2>/dev/null | wc -l)
echo "  Files in archive: $archive_count"

echo ""

# System Resources
echo -e "${BLUE}=== System Resources ===${NC}"
echo "Memory Usage:"
ps aux | grep -E "_v9.py" | grep -v grep | awk '{print "  " $11 ": " $4 "% MEM (" $6/1024 " MB)"}' | head -5

echo ""
echo "Disk Usage (/tmp):"
df -h /tmp | awk 'NR==2 {print "  " $3 " used of " $2 " (" $5 " full)"}'

echo ""

# Overall Status
echo -e "${BLUE}=== Overall Status ===${NC}"
total_components=5
running_count=0
[ $vs_running -eq 0 ] && ((running_count++))
[ $prox_running -eq 0 ] && ((running_count++))
[ $crop_running -eq 0 ] && ((running_count++))
[ $dash_running -eq 0 ] && ((running_count++))
[ $relay_running -eq 0 ] && ((running_count++))

if [ $running_count -eq $total_components ]; then
    echo -e "${GREEN}✓ ALL SYSTEMS OPERATIONAL ($running_count/$total_components components)${NC}"
    exit 0
elif [ $running_count -ge 3 ]; then
    echo -e "${YELLOW}⚠ PARTIAL OPERATION ($running_count/$total_components components running)${NC}"
    exit 1
else
    echo -e "${RED}✗ SYSTEM DOWN ($running_count/$total_components components running)${NC}"
    exit 2
fi

