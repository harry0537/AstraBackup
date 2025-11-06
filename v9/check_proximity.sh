#!/bin/bash
# Quick script to check proximity bridge status

echo "============================================================"
echo "Proximity Bridge Status Check"
echo "============================================================"

# Check if proximity bridge is running
if pgrep -f "combo_proximity_bridge_v9.py" > /dev/null; then
    echo "✓ Proximity Bridge process is running"
    PID=$(pgrep -f "combo_proximity_bridge_v9.py" | head -1)
    echo "  PID: $PID"
else
    echo "✗ Proximity Bridge process NOT running"
fi

echo ""

# Check proximity data file
if [ -f "/tmp/proximity_v9.json" ]; then
    echo "✓ Proximity data file exists"
    echo ""
    echo "Current proximity data:"
    python3 << EOF
import json
import time
from datetime import datetime

try:
    with open('/tmp/proximity_v9.json', 'r') as f:
        data = json.load(f)
    
    sectors = data.get('sectors_cm', [])
    messages_sent = data.get('messages_sent', 0)
    timestamp = data.get('timestamp', 0)
    
    print(f"  Messages sent: {messages_sent}")
    print(f"  Last update: {datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else 'unknown'}")
    print(f"  Vision Server: {'available' if data.get('vision_server_available') else 'unavailable'}")
    print("")
    print("  Sector distances (cm):")
    sector_names = ['FRONT', 'F-RIGHT', 'RIGHT', 'B-RIGHT', 'BACK', 'B-LEFT', 'LEFT', 'F-LEFT']
    for i, (name, dist) in enumerate(zip(sector_names, sectors)):
        dist_m = dist / 100.0
        status = "✓" if dist < 2500 else "─"
        print(f"    {i}: {name:8s} = {int(dist):4d}cm ({dist_m:5.1f}m) {status}")
    
    # Check if all values are max (no detections)
    valid = sum(1 for s in sectors if s < 2500)
    print(f"\n  Valid detections: {valid}/8 sectors")
    
except Exception as e:
    print(f"  Error reading file: {e}")
EOF
else
    echo "✗ Proximity data file NOT found: /tmp/proximity_v9.json"
    echo "  Proximity bridge may not be running or hasn't written data yet"
fi

echo ""
echo "============================================================"
echo "Recent proximity bridge logs (last 20 lines):"
echo "============================================================"
if [ -f "logs/combo_proximity_bridge_v9.out.log" ]; then
    tail -20 logs/combo_proximity_bridge_v9.out.log
else
    echo "No log file found"
fi

echo ""
echo "Recent errors (if any):"
if [ -f "logs/combo_proximity_bridge_v9.err.log" ]; then
    tail -10 logs/combo_proximity_bridge_v9.err.log
else
    echo "No error log file"
fi

