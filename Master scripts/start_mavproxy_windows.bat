@echo off
REM MAVProxy Startup for Windows
REM Update the COM port to match your Pixhawk connection

set PIXHAWK_PORT=COM3
set BAUDRATE=115200
set GROUND_STATION_IP=172.25.2.150
set MAVLINK_PORT=14550

echo 🚀 Starting MAVProxy for Pixhawk 6C (Windows)
echo Port: %PIXHAWK_PORT%
echo Ground Station: %GROUND_STATION_IP%:%MAVLINK_PORT%
echo.
echo Note: Update PIXHAWK_PORT in this script to match your device
echo Check Device Manager for the correct COM port
echo.
mavproxy.py --master=%PIXHAWK_PORT% --baudrate=%BAUDRATE% --out=udp:%GROUND_STATION_IP%:%MAVLINK_PORT%
