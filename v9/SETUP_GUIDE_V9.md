# Project Astra NZ - V9 Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [First Run](#first-run)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Daily Operations](#daily-operations)

---

## Prerequisites

### Hardware Requirements
- **Computer**: Raspberry Pi 4 (4GB+ RAM recommended) or Ubuntu PC
- **RealSense Camera**: Intel D435i or compatible
- **LiDAR**: RPLidar S3 or compatible
- **Flight Controller**: Pixhawk 6C or compatible
- **USB Ports**: 3x USB (camera, LiDAR, Pixhawk)
- **Network**: WiFi or Ethernet for dashboard access

### Software Requirements
- **OS**: Ubuntu 20.04+ or Raspberry Pi OS (64-bit recommended)
- **Python**: 3.8 or higher
- **Virtual Environment**: Recommended

### Permissions
- User must be in `dialout` group for serial port access
- USB device permissions for RealSense

---

## Installation

### Step 1: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install build tools
sudo apt install -y build-essential cmake git python3-dev python3-pip

# Install RealSense SDK (if not already installed)
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE
sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main"
sudo apt update
sudo apt install -y librealsense2-dkms librealsense2-utils librealsense2-dev

# Verify RealSense installation
rs-enumerate-devices

# Add user to dialout group (for serial ports)
sudo usermod -aG dialout $USER

# IMPORTANT: Log out and log back in for group changes to take effect!
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv ~/rover_venv

# Activate virtual environment
source ~/rover_venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install Python Dependencies

```bash
# Navigate to v9 directory
cd /path/to/AstraBackup/v9

# Install all dependencies
pip install pyrealsense2 opencv-python numpy pymavlink rplidar-roboticia flask flask-cors pillow requests

# Verify installations
python3 -c "import pyrealsense2 as rs; print('RealSense OK')"
python3 -c "import cv2; print('OpenCV OK')"
python3 -c "import numpy; print('NumPy OK')"
python3 -c "from rplidar import RPLidar; print('RPLidar OK')"
python3 -c "from pymavlink import mavutil; print('PyMAVLink OK')"
```

### Step 4: Setup udev Rules (Linux Only)

```bash
# Create udev rules file
sudo nano /etc/udev/rules.d/99-astra-v9.rules

# Add these lines:
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2dae", MODE="0666", SYMLINK+="pixhawk"
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", MODE="0666"

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Verify device permissions
ls -l /dev/ttyUSB* /dev/ttyACM*
```

### Step 5: Verify Hardware Connections

```bash
# Check RealSense camera
rs-enumerate-devices

# Check LiDAR (should see data scrolling)
ls /dev/ttyUSB*
# If you see /dev/ttyUSB0, LiDAR is likely connected

# Check Pixhawk
ls /dev/ttyACM*
# If you see /dev/ttyACM0, Pixhawk is likely connected
```

---

## Configuration

### Edit Configuration File

```bash
cd /path/to/AstraBackup/v9
nano rover_config_v9.json
```

**Key settings to verify/change**:

```json
{
  "proximity_bridge": {
    "lidar_port": "/dev/ttyUSB0",     # Change if different
    "pixhawk_port": "/dev/ttyACM0"   # Change if different
  },
  
  "dashboard": {
    "ip": "10.244.77.186",            # Change to your dashboard PC IP
    "port": 8081
  },
  
  "crop_monitor": {
    "capture_interval_seconds": 10    # Adjust as needed
  }
}
```

### Make Scripts Executable (Linux)

```bash
chmod +x start_rover_v9.sh
chmod +x stop_rover_v9.sh
chmod +x check_v9_health.sh
```

---

## First Run

### Option A: Using Rover Manager (Recommended)

```bash
cd /path/to/AstraBackup/v9

# Activate virtual environment
source ~/rover_venv/bin/activate

# Start all components
python3 rover_manager_v9.py
```

The rover manager will:
1. Check if V9 is already running
2. Create necessary directories
3. Start Vision Server first (critical!)
4. Wait for Vision Server to be ready
5. Start Proximity Bridge
6. Start Crop Monitor
7. Start Dashboard
8. Start Data Relay
9. Monitor components and auto-stop on failure

**Press Ctrl+C to stop all components cleanly**

### Option B: Using Bash Script (Linux Only)

```bash
cd /path/to/AstraBackup/v9

# Start all components
./start_rover_v9.sh
```

### Option C: Manual Start (For Debugging)

```bash
cd /path/to/AstraBackup/v9
source ~/rover_venv/bin/activate

# Terminal 1: Vision Server (MUST START FIRST)
python3 realsense_vision_server_v9.py

# Wait 5 seconds, then in Terminal 2: Proximity Bridge
python3 combo_proximity_bridge_v9.py

# Terminal 3: Crop Monitor
python3 simple_crop_monitor_v9.py

# Terminal 4: Dashboard
python3 telemetry_dashboard_v9.py

# Terminal 5: Data Relay (optional)
python3 data_relay_v9.py
```

---

## Verification

### Check Component Status

```bash
# Run health check
./check_v9_health.sh

# Expected output:
# ✓ Vision Server: RUNNING
# ✓ Proximity Bridge: RUNNING
# ✓ Crop Monitor: RUNNING
# ✓ Dashboard: RUNNING
# ✓ Data Relay: RUNNING
```

### Check Vision Server Output

```bash
# Check if RGB frames are being written
ls -lh /tmp/vision_v9/rgb_latest.jpg

# Should show a file that's recently modified (< 1 second ago)

# Check Vision Server status
cat /tmp/vision_v9/status.json | python3 -m json.tool

# Should show:
# "status": "RUNNING"
# "fps": { "rgb_actual": ~15, "depth_actual": ~15 }
```

### Check Proximity Data

```bash
# View proximity data
cat /tmp/proximity_v9.json | python3 -m json.tool

# Should show 8 sectors with distances
```

### Check Crop Monitor

```bash
# Check crop monitor status
cat /tmp/crop_monitor_v9.json | python3 -m json.tool

# Check archived images
ls -lh /tmp/crop_archive/

# Should see crop_YYYYMMDD_HHMMSS.jpg files
```

### Access Dashboard

Open a web browser and navigate to:
- **Remote**: `http://10.244.77.186:8081` (change IP to your dashboard PC)
- **Local**: `http://localhost:8081`

**Default Login**:
- Username: `admin`
- Password: `admin`

You should see:
- ✅ Live video stream from Vision Server
- ✅ Proximity radar updating
- ✅ System status showing all components green
- ✅ Crop images in gallery

---

## Troubleshooting

### Vision Server Won't Start

**Error**: "Camera connection failed"

```bash
# Check if camera is connected
rs-enumerate-devices

# Check USB connection
lsusb | grep Intel

# Check if camera is being used by another process
lsof | grep video

# If V8 is running, stop it first
pkill -f _v8.py
```

**Error**: "Another Vision Server is already running"

```bash
# Check if Vision Server is actually running
ps aux | grep realsense_vision_server_v9

# If not running, remove stale lock file
rm /tmp/vision_v9/.lock
```

### Proximity Bridge Can't Find Depth Data

**Error**: "Vision Server unavailable, using LiDAR-only mode"

```bash
# Check if Vision Server is running
./check_v9_health.sh

# Check if depth files exist
ls -lh /tmp/vision_v9/depth_*

# Check Vision Server logs
tail -f /tmp/vision_v9/vision_server.log

# Restart Vision Server
pkill -f realsense_vision_server_v9.py
python3 realsense_vision_server_v9.py
```

### Crop Monitor Not Capturing Images

**Error**: "Vision Server image not available"

```bash
# Check if RGB file exists and is recent
ls -lh /tmp/vision_v9/rgb_latest.jpg
stat /tmp/vision_v9/rgb_latest.jpg

# Check Vision Server status
cat /tmp/vision_v9/status.json

# Check if opencv is installed
python3 -c "import cv2; print(cv2.__version__)"
```

### LiDAR Not Detected

**Error**: "RPLidar not found"

```bash
# Check if LiDAR is connected
ls -l /dev/ttyUSB*

# Check USB power (LiDAR needs good power)
lsusb

# Try different USB port

# Check if device is in use
lsof | grep ttyUSB

# Check permissions
ls -l /dev/ttyUSB0
# Should show: crw-rw-rw- (666 permissions)
```

### Pixhawk Not Detected

**Error**: "No Pixhawk port available"

```bash
# Check if Pixhawk is connected
ls -l /dev/ttyACM*

# Check if MAVLink messages are coming through
mavproxy.py --master=/dev/ttyACM0 --baudrate=57600

# Check permissions
ls -l /dev/ttyACM0
# Should show: crw-rw---- (group readable/writable)
# User must be in dialout group!

# Verify group membership
groups | grep dialout
# If not in dialout group:
sudo usermod -aG dialout $USER
# Then logout and login again!
```

### Dashboard Not Accessible

**Error**: Can't access `http://10.244.77.186:8081`

```bash
# Check if dashboard is running
ps aux | grep telemetry_dashboard_v9.py

# Check what port it's using
netstat -tuln | grep 808

# Check firewall
sudo ufw status
# If firewall is blocking, allow port:
sudo ufw allow 8081/tcp

# Test locally first
curl http://localhost:8081

# Check network connectivity
ping 10.244.77.186
```

### High CPU Usage

```bash
# Check which component is using CPU
top

# Vision Server high CPU (>40%) is expected at 15 FPS
# If others are high, check for errors:
./check_v9_health.sh

# Reduce FPS in config if needed
nano rover_config_v9.json
# Change: "fps": 10  (from 15)
```

### Disk Space Full

```bash
# Check disk usage
df -h /tmp

# Clean up old crop images
rm /tmp/crop_archive/crop_202* # Delete old images

# Reduce max archived images
nano rover_config_v9.json
# Change: "max_archived_images": 5  (from 10)
```

---

## Daily Operations

### Starting the System

```bash
cd /path/to/AstraBackup/v9
source ~/rover_venv/bin/activate
python3 rover_manager_v9.py
```

### Stopping the System

```bash
# If using rover_manager: Press Ctrl+C

# Or use stop script:
./stop_rover_v9.sh

# Or manual:
pkill -f _v9.py
```

### Checking System Health

```bash
# Run health check
./check_v9_health.sh

# Watch live updates (every 5 seconds)
watch -n 5 ./check_v9_health.sh
```

### Viewing Logs

```bash
# Vision Server logs
tail -f /tmp/vision_v9/vision_server.log

# All component status
tail -f /tmp/vision_v9/status.json
tail -f /tmp/proximity_v9.json
tail -f /tmp/crop_monitor_v9.json
```

### Restarting a Single Component

```bash
# Example: Restart Crop Monitor
pkill -f simple_crop_monitor_v9.py
python3 simple_crop_monitor_v9.py &

# Note: Vision Server should almost never need restart
# If it does, restart ALL components!
```

### Emergency Rollback to V8

```bash
# Stop V9
pkill -f _v9.py

# Start V8
cd ../v8
python3 rover_manager_v8.py
```

### Backup Critical Data

```bash
# Backup crop images
tar -czf crop_backup_$(date +%Y%m%d).tar.gz /tmp/crop_archive/

# Backup configuration
cp rover_config_v9.json rover_config_v9.json.backup
```

---

## Performance Tuning

### For Raspberry Pi 3 (Lower Power)

```json
// rover_config_v9.json
{
  "vision_server": {
    "rgb_resolution": [424, 240],  // Lower resolution
    "depth_resolution": [424, 240],
    "fps": 10  // Lower FPS
  },
  "crop_monitor": {
    "capture_interval_seconds": 15  // Less frequent
  }
}
```

### For High Performance (Desktop PC)

```json
// rover_config_v9.json
{
  "vision_server": {
    "rgb_resolution": [848, 480],  // Higher resolution
    "depth_resolution": [848, 480],
    "fps": 30  // Higher FPS
  },
  "crop_monitor": {
    "capture_interval_seconds": 5  // More frequent
  }
}
```

---

## Auto-Start on Boot (Optional)

### Create Systemd Service

```bash
sudo nano /etc/systemd/system/astra-rover-v9.service
```

```ini
[Unit]
Description=Project Astra NZ Rover V9
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/AstraBackup/v9
Environment="PATH=/home/pi/rover_venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/home/pi/rover_venv/bin/python3 /home/pi/AstraBackup/v9/rover_manager_v9.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable astra-rover-v9.service
sudo systemctl start astra-rover-v9.service

# Check status
sudo systemctl status astra-rover-v9.service

# View logs
sudo journalctl -u astra-rover-v9.service -f
```

---

## Maintenance Schedule

### Daily
- Check system health: `./check_v9_health.sh`
- Verify dashboard is accessible
- Check disk space: `df -h /tmp`

### Weekly
- Review logs for errors
- Clean old crop images if needed
- Verify all sensors working

### Monthly
- Update system packages: `sudo apt update && sudo apt upgrade`
- Update Python packages: `pip install --upgrade pyrealsense2 opencv-python`
- Backup configuration files
- Review performance metrics

---

## Support and Documentation

### Additional Resources
- **Architecture**: See `DETAILED_ARCHITECTURE.md`
- **Implementation Plan**: See `IMPLEMENTATION_PLAN.md`
- **Bug Fixes**: See `BUG_FIXES_V9.md`
- **V8 vs V9 Comparison**: See `V8_VS_V9_COMPARISON.md`

### Getting Help
1. Check troubleshooting section above
2. Run health check: `./check_v9_health.sh`
3. Check logs in `/tmp/vision_v9/`
4. Try emergency rollback to V8

---

**Version**: V9.0
**Last Updated**: 2025-10-31
**Status**: Ready for Deployment

