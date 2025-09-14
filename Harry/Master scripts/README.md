# Autonomous Rover Scripts

Scripts for RPLidar S3 + Pixhawk 6C + ArduPilot setup.

## For Ubuntu/Linux (your rover):

1. Test LiDAR: `python3 rplidar_test.py`
2. Start MAVProxy: `./start_mavproxy.sh` (use Git Bash)  
3. Start bridge: `python3 lidar_mavlink_bridge.py`
4. Test data: `python3 test_proximity_data.py`

## For Windows (development):

1. Use `start_mavproxy_windows.bat` (update COM port first)
2. Run Python scripts same way

## Mission Planner Connection:
- UDP connection on port 14550
- Check Proximity tab for 72 sectors

## Your Working Configuration:
```
mavproxy.py --master=/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00 --baudrate 115200 --out udp:172.25.2.150:14550
```
