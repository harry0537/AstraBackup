#!/bin/bash
# MAVProxy Startup Script for Pixhawk 6C
# Note: Run this in Git Bash or WSL, not Windows Command Prompt

PIXHAWK_DEVICE="/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00"
BAUDRATE="115200"
GROUND_STATION_IP="172.25.2.150"
MAVLINK_PORT="14550"

echo "🚀 Starting MAVProxy for Pixhawk 6C"
echo "Device: $PIXHAWK_DEVICE"
echo "Ground Station: $GROUND_STATION_IP:$MAVLINK_PORT"

mavproxy.py --master=$PIXHAWK_DEVICE --baudrate=$BAUDRATE --out=udp:$GROUND_STATION_IP:$MAVLINK_PORT
