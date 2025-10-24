#!/bin/bash
# Clean start script for Rover V8

echo "=========================================="
echo "Starting Project Astra NZ - Rover V8"
echo "=========================================="

# Kill any existing processes
echo "Stopping existing processes..."
pkill -f rover_manager || true
pkill -f combo_proximity_bridge || true
pkill -f simple_crop_monitor || true
pkill -f telemetry_dashboard || true
pkill -f data_relay || true
sleep 2

# Clean up old temp files
echo "Cleaning temp files..."
rm -f /tmp/crop_latest.jpg
rm -rf /tmp/rover_vision
rm -f /tmp/crop_monitor_v8.json
rm -f /tmp/proximity_v8.json

# Create fresh directories
mkdir -p /tmp/rover_vision
mkdir -p /tmp/crop_archive

echo "Starting rover manager..."
python3 rover_manager_v8.py

