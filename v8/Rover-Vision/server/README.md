# Rover-Vision Server

## 🚀 Professional Rover Telemetry System

Rover-Vision is a comprehensive rover telemetry and monitoring system designed for autonomous rover operations. This is the **server component** that runs on the Ubuntu rover hardware.

## 📋 Features

- **Modern Dashboard**: Compact single-screen telemetry interface
- **Space Optimization**: Rolling buffer image management (40 images max)
- **Real-time Monitoring**: 1-second refresh rate with live data
- **Hardware Integration**: RPLidar, Pixhawk, RealSense camera support
- **Auto-Restart**: Automatic component recovery and management
- **Virtual Environment**: Isolated Python environment for stability
- **Service Integration**: Optional systemd service for auto-start

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ROVER-VISION SERVER                      │
├─────────────────────────────────────────────────────────────┤
│  🖥️  Rover Manager    │  📊  Telemetry Dashboard          │
│  - Component mgmt     │  - Web interface (port 8081)     │
│  - Auto-restart       │  - Real-time data display         │
│  - System monitoring  │  - Compact single-screen layout   │
├─────────────────────────────────────────────────────────────┤
│  🔍  Proximity Bridge  │  📹  Crop Monitor                 │
│  - LiDAR + RealSense  │  - Space-optimized imaging       │
│  - MAVLink integration │  - Rolling buffer (40 images)    │
│  - Sensor data fusion  │  - 60-second capture interval    │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Installation

### Prerequisites
- Ubuntu 18.04+ (rover hardware)
- Python 3.7+
- RPLidar, Pixhawk, RealSense camera
- User in dialout group

### Install
```bash
# Download and install
wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-server.tar.gz
tar -xzf rover-vision-server.tar.gz
cd rover-vision-server
sudo ./install.sh
```

### Start System
```bash
# Start rover system
rover-vision start

# Check status
rover-vision status

# View dashboard
# Local: http://0.0.0.0:8081
# Network: http://ROVER_IP:8081
```

## 📖 Usage

### Basic Commands
```bash
rover-vision start      # Start the rover system
rover-vision stop       # Stop the rover system
rover-vision restart    # Restart the rover system
rover-vision status     # Show system status
rover-vision logs       # View system logs
rover-vision config     # Edit configuration
rover-vision update     # Update to latest version
```

### Dashboard Access
- **Local**: `http://0.0.0.0:8081`
- **Network**: `http://ROVER_IP:8081`
- **ZeroTier**: `http://ZEROTIER_IP:8081`

## ⚙️ Configuration

### Main Config File
```bash
sudo nano /opt/rover-vision/config/rover_config.json
```

### Key Settings
```json
{
  "dashboard": {
    "ip": "0.0.0.0",
    "port": 8081
  },
  "hardware": {
    "lidar_port": "/dev/ttyUSB0",
    "pixhawk_port": "/dev/ttyACM0"
  },
  "crop_monitor": {
    "interval": 60,
    "max_images": 40,
    "quality": 60
  }
}
```

## 🔧 Troubleshooting

### Check System Status
```bash
rover-vision status
systemctl status rover-vision
```

### View Logs
```bash
rover-vision logs
journalctl -u rover-vision -f
```

### Restart Components
```bash
rover-vision restart
```

### Hardware Issues
```bash
# Check hardware connections
rover-vision diagnose

# Reset camera
rover-vision reset-camera

# Check permissions
rover-vision check-permissions
```

## 📁 File Structure

```
/opt/rover-vision/
├── bin/                    # Executable scripts
│   ├── rover-vision       # Main control script
│   └── rover-manager      # Component manager
├── config/                # Configuration files
│   ├── rover_config.json  # Main configuration
│   └── components.json    # Component definitions
├── scripts/                # Python scripts
│   ├── telemetry_dashboard.py
│   ├── simple_crop_monitor.py
│   └── combo_proximity_bridge.py
├── logs/                  # System logs
├── data/                  # Runtime data
│   ├── images/            # Crop monitor images
│   └── telemetry/         # Telemetry data
└── venv/                  # Virtual environment
```

## 🔄 Updates

### Update System
```bash
rover-vision update
```

### Manual Update
```bash
cd /opt/rover-vision
git pull origin main
sudo ./install.sh
```

## 📞 Support

- **Documentation**: `/opt/rover-vision/docs/`
- **Logs**: `/opt/rover-vision/logs/`
- **Config**: `/opt/rover-vision/config/`
- **Issues**: GitHub Issues

---

**Rover-Vision Server** - Professional rover telemetry system for autonomous operations.
