# Project Astra NZ - V9 Scripts Documentation

## 🚀 Overview

Project Astra NZ V9 is a modern, space-optimized rover telemetry system designed for autonomous rover operations. The V9 system features a compact, single-screen dashboard, space-saving image management, and enhanced system monitoring.

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Script Functions](#script-functions)
3. [Installation & Setup](#installation--setup)
4. [Usage Instructions](#usage-instructions)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [File Structure](#file-structure)

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    ROVER SYSTEM V9                          │
├─────────────────────────────────────────────────────────────┤
│  🖥️  Rover Manager V9    │  📊  Telemetry Dashboard V9     │
│  - Component management  │  - Web interface (port 8081)   │
│  - Auto-restart logic    │  - Real-time data display       │
│  - System monitoring     │  - Compact single-screen layout │
├─────────────────────────────────────────────────────────────┤
│  🔍  Proximity Bridge V9  │  📹  Crop Monitor V9            │
│  - LiDAR + RealSense     │  - Space-optimized imaging     │
│  - MAVLink integration   │  - Rolling buffer (40 images)   │
│  - Sensor data fusion    │  - 60-second capture interval   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Hardware Sensors → Proximity Bridge → /tmp/proximity_v8.json → Dashboard
RealSense Camera → Crop Monitor → /tmp/crop_latest.jpg → Dashboard
Pixhawk GPS → Proximity Bridge → MAVLink → Dashboard
```

## 📝 Script Functions

### 1. `telemetry_dashboard_v9.py` - Modern Web Dashboard

**Purpose:** Real-time rover telemetry monitoring interface

**Key Features:**
- **Compact Layout:** Single-screen design with no scrolling
- **Real-time Updates:** 1-second refresh rate with smooth animations
- **Modern UI:** Dark theme with neon accents and color-coded status
- **Proximity Radar:** Interactive 360-degree obstacle visualization
- **Live Vision:** Real-time rover camera feed with image streaming
- **System Monitoring:** CPU, memory, disk usage tracking
- **GPS Integration:** MAVLink GPS coordinates and navigation data
- **Power Monitoring:** Battery status and power consumption

**Components Displayed:**
- **System Status:** Component health and uptime
- **Sensor Health:** LiDAR, RealSense, Pixhawk status
- **GPS Data:** Coordinates, altitude, heading, satellites
- **Power Data:** Battery voltage, current, percentage
- **Navigation:** Flight mode, armed status, GPS accuracy
- **Proximity Radar:** 8-sector obstacle detection
- **Rover Vision:** Live camera feed with status

**Technical Details:**
- **Framework:** Flask web server
- **Port:** 8081 (configurable)
- **Data Sources:** `/tmp/proximity_v8.json`, `/tmp/crop_monitor_v9.json`
- **Updates:** JavaScript polling every 1000ms
- **Responsive:** Adapts to different screen sizes

**Usage:**
```bash
python3 telemetry_dashboard_v9.py
# Access: http://0.0.0.0:8081 (local) or http://172.25.77.186:8081 (network)
```

### 2. `simple_crop_monitor_v9.py` - Space-Optimized Image Capture

**Purpose:** Captures and manages rover vision images with space efficiency

**Key Features:**
- **Space Optimization:** Rolling buffer of maximum 40 images
- **Automatic Cleanup:** Removes oldest images when limit exceeded
- **Optimized Compression:** 60% JPEG quality for smaller files
- **Camera Sharing:** Works alongside proximity bridge without conflicts
- **Storage Monitoring:** Tracks disk usage and image statistics
- **Error Handling:** Automatic reconnection on camera failures
- **Status Reporting:** Writes status to `/tmp/crop_monitor_v9.json`

**Space-Saving Features:**
- **Rolling Buffer:** Maximum 40 images stored at any time
- **Automatic Cleanup:** Removes oldest images when limit reached
- **Optimized Quality:** 60% JPEG compression for space efficiency
- **Timestamped Files:** `crop_YYYYMMDD_HHMMSS.jpg` format
- **Storage Tracking:** Monitors total size and average file size

**Camera Integration:**
- **Resource Sharing:** Multiple fallback configurations
- **Conflict Resolution:** Handles "Device or resource busy" errors
- **Native Profiles:** Uses device's optimal stream configurations
- **Minimal Fallback:** Ultra-low resolution if needed
- **Automatic Reconnection:** Reconnects on camera failures

**Configuration:**
- **Capture Interval:** 60 seconds (configurable)
- **Max Images:** 40 (configurable)
- **Image Quality:** 60% JPEG (configurable)
- **Storage Directory:** `/tmp/crop_images/`
- **Latest Image:** `/tmp/crop_latest.jpg`

**Usage:**
```bash
python3 simple_crop_monitor_v9.py
```

### 3. `rover_manager_v9.py` - Enhanced System Management

**Purpose:** Manages and monitors all rover components with auto-restart

**Key Features:**
- **Component Management:** Starts, stops, and monitors all rover scripts
- **Auto-Restart:** Automatically restarts failed critical components
- **System Monitoring:** CPU, memory, disk usage tracking
- **Virtual Environment:** Automatically uses rover virtual environment
- **Enhanced Logging:** Timestamped logs with component tracking
- **Resource Management:** Monitors system resources and performance
- **Status Display:** Real-time component status and statistics

**Managed Components:**
- **Proximity Bridge (195):** Critical - LiDAR and RealSense fusion
- **Data Relay (197):** Optional - Data transmission
- **Crop Monitor (198):** Optional - Image capture
- **Telemetry Dashboard (199):** Optional - Web interface

**Monitoring Features:**
- **Component Status:** Running/stopped with uptime tracking
- **Restart Tracking:** Counts and limits component restarts
- **System Stats:** CPU usage, memory consumption, disk space
- **Proximity Data:** Real-time obstacle detection display
- **Storage Monitoring:** Crop monitor storage statistics
- **Error Handling:** Graceful shutdown and cleanup

**Virtual Environment Support:**
- **Auto-Detection:** Finds and uses `~/rover_venv/bin/python3`
- **Fallback:** Uses system Python with warning if venv not found
- **Logging:** Shows which Python executable is being used
- **Component Isolation:** Each component runs in virtual environment

**Usage:**
```bash
python3 rover_manager_v9.py
# Optional: python3 rover_manager_v9.py --auto (for service mode)
```

### 4. `rover_setup_v9.py` - Installation & Configuration

**Purpose:** Automated setup and configuration of the V9 rover system

**Key Features:**
- **Dependency Installation:** Installs all required Python packages
- **Virtual Environment:** Creates and configures `~/rover_venv`
- **Hardware Detection:** Auto-detects LiDAR, Pixhawk, RealSense
- **Permission Setup:** Configures device permissions and udev rules
- **Network Configuration:** Detects and configures network settings
- **Storage Optimization:** Sets up log rotation and cleanup
- **Service Creation:** Optional systemd service for auto-start

**Setup Process:**
1. **Python Dependencies:** Installs all required packages in virtual environment
2. **Permissions:** Configures device permissions and udev rules
3. **Network:** Detects rover IP and configures network settings
4. **Hardware:** Auto-detects and configures all hardware components
5. **Storage:** Sets up log rotation and storage optimization
6. **Service:** Optional systemd service creation

**Hardware Detection:**
- **RPLidar:** Tests multiple ports and validates LiDAR connection
- **Pixhawk:** Detects autopilot via MAVLink heartbeat
- **RealSense:** Tests multiple camera configurations
- **Permissions:** Verifies user is in dialout group
- **Storage:** Checks available disk space

**Configuration Output:**
- **Config File:** `rover_config_v9.json` with all settings
- **Virtual Environment:** `~/rover_venv` with all dependencies
- **Device Rules:** `/etc/udev/rules.d/99-astra-v9.rules`
- **Log Rotation:** `/etc/logrotate.d/astra-v9`
- **Service:** `/etc/systemd/system/astra-rover-v9.service`

**Usage:**
```bash
python3 rover_setup_v9.py
# For service creation: sudo python3 rover_setup_v9.py
```

### 5. `rover_config_v9.json` - System Configuration

**Purpose:** Central configuration file for all V9 components

**Configuration Sections:**
- **Dashboard:** IP address, port, network settings
- **Hardware:** LiDAR port, Pixhawk port, RealSense settings
- **Crop Monitor:** Capture interval, max images, quality settings
- **Proximity Bridge:** Sector count, distance limits, MAVLink settings
- **Data Relay:** Enable/disable, relay interval
- **Telemetry Dashboard:** Refresh rate, feature toggles

**Key Settings:**
```json
{
  "dashboard_ip": "0.0.0.0",
  "dashboard_port": 8081,
  "rover_ip": "172.25.77.186",
  "lidar_port": "/dev/ttyUSB0",
  "pixhawk_port": "/dev/ttyACM0",
  "crop_monitor": {
    "interval": 60,
    "max_images": 40,
    "quality": 60
  }
}
```

### 6. `activate_rover_venv.sh` - Virtual Environment Activator

**Purpose:** Easy activation of the rover virtual environment

**Features:**
- **Environment Detection:** Checks if virtual environment exists
- **Activation:** Sources the virtual environment
- **Path Display:** Shows Python and pip paths
- **Usage Instructions:** Provides clear next steps
- **Persistent Shell:** Keeps environment active

**Usage:**
```bash
./activate_rover_venv.sh
# Then run: python3 rover_manager_v9.py
```

## 🚀 Installation & Setup

### Prerequisites

- **Operating System:** Ubuntu Linux (rover hardware)
- **Python:** Python 3.7+ with venv support
- **Hardware:** RPLidar, Pixhawk, RealSense camera
- **Permissions:** User in dialout group
- **Network:** ZeroTier for remote access (optional)

### Quick Setup

1. **Clone Repository:**
   ```bash
   git clone https://github.com/your-repo/astra-v9.git
   cd astra-v9
   ```

2. **Run Setup:**
   ```bash
   python3 rover_setup_v9.py
   ```

3. **Activate Environment:**
   ```bash
   source ~/rover_venv/bin/activate
   # Or use: ./activate_rover_venv.sh
   ```

4. **Start System:**
   ```bash
   python3 rover_manager_v9.py
   ```

5. **Access Dashboard:**
   - Local: `http://0.0.0.0:8081`
   - Network: `http://172.25.77.186:8081`

### Detailed Setup

#### Step 1: System Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3-venv python3-pip git -y

# Add user to dialout group
sudo usermod -aG dialout $USER
# Logout and login again
```

#### Step 2: Hardware Connection
- **RPLidar:** Connect to USB port (usually `/dev/ttyUSB0`)
- **Pixhawk:** Connect to USB port (usually `/dev/ttyACM0`)
- **RealSense:** Connect to USB port
- **Power:** Ensure stable power supply

#### Step 3: Software Installation
```bash
# Run automated setup
python3 rover_setup_v9.py

# For service creation (optional)
sudo python3 rover_setup_v9.py
```

#### Step 4: Verification
```bash
# Check virtual environment
source ~/rover_venv/bin/activate
python3 -c "import rplidar, pyrealsense2, pymavlink; print('All libraries OK')"

# Test hardware
python3 rover_setup_v9.py  # Will detect hardware
```

## 📖 Usage Instructions

### Starting the System

1. **Activate Virtual Environment:**
   ```bash
   source ~/rover_venv/bin/activate
   ```

2. **Start Rover Manager:**
   ```bash
   python3 rover_manager_v9.py
   ```

3. **Access Dashboard:**
   - Open browser to `http://0.0.0.0:8081`
   - Or network access: `http://172.25.77.186:8081`

### Individual Component Usage

#### Telemetry Dashboard
```bash
python3 telemetry_dashboard_v9.py
# Simulation mode: python3 telemetry_dashboard_v9.py --simulate
```

#### Crop Monitor
```bash
python3 simple_crop_monitor_v9.py
```

#### Proximity Bridge
```bash
python3 combo_proximity_bridge_v9.py
```

### Service Management (Optional)

```bash
# Enable auto-start
sudo systemctl enable astra-rover-v9.service

# Start service
sudo systemctl start astra-rover-v9.service

# Stop service
sudo systemctl stop astra-rover-v9.service

# Check status
sudo systemctl status astra-rover-v9.service
```

## ⚙️ Configuration

### Dashboard Configuration

Edit `rover_config_v9.json`:
```json
{
  "dashboard_ip": "0.0.0.0",
  "dashboard_port": 8081,
  "rover_ip": "172.25.77.186"
}
```

### Crop Monitor Configuration

```json
{
  "crop_monitor": {
    "interval": 60,      // Capture interval (seconds)
    "max_images": 40,    // Maximum images to store
    "quality": 60        // JPEG quality (0-100)
  }
}
```

### Hardware Configuration

```json
{
  "lidar_port": "/dev/ttyUSB0",
  "pixhawk_port": "/dev/ttyACM0",
  "realsense_config": {
    "width": 640,
    "height": 480,
    "fps": 15
  }
}
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Virtual Environment Issues
**Problem:** "No module named 'rplidar'"
**Solution:**
```bash
# Activate virtual environment
source ~/rover_venv/bin/activate

# Verify installation
pip list | grep rplidar
```

#### 2. Camera Conflicts
**Problem:** "Device or resource busy"
**Solution:**
```bash
# Kill existing processes
sudo pkill -f realsense
sudo pkill -f crop_monitor

# Restart components
python3 rover_manager_v9.py
```

#### 3. Permission Issues
**Problem:** "Permission denied" on device access
**Solution:**
```bash
# Add user to dialout group
sudo usermod -aG dialout $USER

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logout and login again
```

#### 4. Dashboard Not Loading
**Problem:** Dashboard shows "Connection refused"
**Solution:**
```bash
# Check if dashboard is running
ps aux | grep telemetry_dashboard

# Check port availability
netstat -tlnp | grep 8081

# Restart dashboard
python3 telemetry_dashboard_v9.py
```

#### 5. Storage Issues
**Problem:** "No space left on device"
**Solution:**
```bash
# Check disk space
df -h /tmp

# Clean old images
rm /tmp/crop_images/crop_*.jpg

# Check crop monitor settings
grep -A 5 "crop_monitor" rover_config_v9.json
```

### Debug Mode

#### Enable Debug Logging
```bash
# Run with debug output
python3 telemetry_dashboard_v9.py --debug
python3 simple_crop_monitor_v9.py --debug
```

#### Check Log Files
```bash
# View component logs
tail -f logs/telemetry_dashboard_v9.out.log
tail -f logs/simple_crop_monitor_v9.err.log
```

#### System Diagnostics
```bash
# Check hardware
lsusb | grep -E "(RealSense|Pixhawk|RPLidar)"

# Check permissions
groups $USER

# Check virtual environment
which python3
python3 -c "import sys; print(sys.path)"
```

## 📁 File Structure

```
astra-v9/
├── telemetry_dashboard_v9.py      # Web dashboard interface
├── simple_crop_monitor_v9.py      # Space-optimized image capture
├── rover_manager_v9.py            # System management
├── rover_setup_v9.py             # Installation script
├── rover_config_v9.json          # Configuration file
├── activate_rover_venv.sh         # Virtual environment activator
├── logs/                          # Component log files
│   ├── telemetry_dashboard_v9.out.log
│   ├── simple_crop_monitor_v9.out.log
│   └── rover_manager_v9.out.log
└── /tmp/                          # Runtime data
    ├── proximity_v8.json          # Proximity sensor data
    ├── crop_monitor_v9.json       # Crop monitor status
    ├── crop_latest.jpg            # Latest rover vision image
    └── crop_images/               # Image storage directory
        ├── crop_20241201_143022.jpg
        ├── crop_20241201_143122.jpg
        └── ...
```

## 🎯 Key Features Summary

### V9 Improvements Over V8

1. **Modern Dashboard:**
   - Single-screen layout (no scrolling)
   - Dark theme with neon accents
   - Real-time updates with animations
   - Enhanced GPS and power monitoring

2. **Space Optimization:**
   - Rolling buffer of 40 images maximum
   - Automatic cleanup of old images
   - 60% JPEG compression for smaller files
   - Storage monitoring and reporting

3. **Enhanced Management:**
   - Better virtual environment handling
   - Improved error handling and reconnection
   - System resource monitoring
   - Enhanced logging and diagnostics

4. **Robust Operation:**
   - Camera resource sharing
   - Automatic component restart
   - Graceful error handling
   - Service integration

### Performance Characteristics

- **Dashboard Refresh:** 1 second
- **Image Capture:** 60 seconds
- **Storage Limit:** 40 images (~50-100MB)
- **Memory Usage:** ~100-200MB per component
- **CPU Usage:** ~5-15% per component
- **Network:** HTTP on port 8081

## 📞 Support

For issues and questions:
1. Check this documentation first
2. Review log files in `logs/` directory
3. Run diagnostic scripts
4. Check hardware connections
5. Verify virtual environment setup

## 🔄 Updates

To update the system:
1. Backup current configuration: `cp rover_config_v9.json rover_config_v9.json.backup`
2. Pull latest changes: `git pull origin main`
3. Re-run setup: `python3 rover_setup_v9.py`
4. Restart system: `python3 rover_manager_v9.py`

---

**Project Astra NZ V9** - Modern, space-optimized rover telemetry system for autonomous operations.
