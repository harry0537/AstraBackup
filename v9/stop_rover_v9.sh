#!/bin/bash
# Project Astra NZ - V9 Stop Script
# Stops all V9 components cleanly (like v8 stop behavior)

echo "Stopping all V9 components..."

# Stop all V9 processes
pkill -f "realsense_vision_server_v9.py" 2>/dev/null || true
pkill -f "combo_proximity_bridge_v9.py" 2>/dev/null || true
pkill -f "simple_crop_monitor_v9.py" 2>/dev/null || true
pkill -f "telemetry_dashboard_v9.py" 2>/dev/null || true
pkill -f "data_relay_v9.py" 2>/dev/null || true

# Wait a moment
sleep 2

# Force kill if still running
pkill -9 -f "_v9.py" 2>/dev/null || true

echo "✓ Done"
