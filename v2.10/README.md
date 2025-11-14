# Project Astra NZ - Autonomous Rover System v2.10

**Stable Release - Simple Setup and Operation**

---

## 🚀 Quick Start

### Step 1: Run Setup Script

```bash
python3 rover_setup.py
```

This will:
- Check Python version
- Install system dependencies
- Create virtual environment
- Install Python packages
- Create configuration file

### Step 2: Configure Hardware

Edit `rover_config.json` to match your hardware:

```json
{
  "dashboard_ip": "0.0.0.0",
  "dashboard_port": 8081,
  "mavlink_port": 14550,
  "lidar_port": "/dev/ttyUSB0",
  "pixhawk_port": "/dev/ttyACM0"
}
```

### Step 3: Connect Hardware

- Connect Pixhawk 6C flight controller
- Connect RPLiDAR S3 sensor
- Connect Intel RealSense D435i camera
- Ensure all USB devices are recognized

### Step 4: Start the Rover System

```bash
python3 rover_manager.py
```

The system will automatically start all components in the correct order:
1. Vision Server (RealSense camera)
2. Proximity Bridge (LiDAR obstacle detection)
3. Data Relay (Cloud connectivity)
4. Crop Monitor (Image capture)
5. Dashboard (Web interface)

### Step 5: Access Dashboard

Open your web browser and navigate to:

**http://localhost:8081**

- Username: `admin`
- Password: `admin`

---

## 📋 System Components

### Core Components

- **rover_manager.py** - Main startup manager (start this first)
- **realsense_vision_server.py** - RealSense camera control
- **combo_proximity_bridge.py** - LiDAR obstacle detection
- **telemetry_dashboard.py** - Web dashboard interface
- **data_relay.py** - Cloud data relay
- **simple_crop_monitor.py** - Crop image capture
- **obstacle_navigation.py** - Autonomous obstacle navigation

### Configuration

- **rover_config.json** - Main configuration file
- **config/rover_baseline_v9.param** - ArduPilot parameters

### Tools

- **tools/apply_params.py** - Apply ArduPilot parameters

---

## 🔧 Manual Component Startup

If you need to run components individually:

```bash
# 1. Start Vision Server (must be first)
python3 realsense_vision_server.py

# 2. Start Proximity Bridge
python3 combo_proximity_bridge.py

# 3. Start Dashboard
python3 telemetry_dashboard.py

# 4. Start Data Relay (optional)
python3 data_relay.py

# 5. Start Crop Monitor (optional)
python3 simple_crop_monitor.py

# 6. Start Obstacle Navigation (optional)
python3 obstacle_navigation.py
```

---

## 📖 Requirements

### Hardware
- Pixhawk 6C flight controller
- RPLiDAR S3 sensor
- Intel RealSense D435i camera
- Ubuntu 20.04+ or Raspberry Pi OS (64-bit)
- USB ports for all devices

### Software
- Python 3.8 or higher
- Virtual environment (created by setup script)

---

## 🛠️ Troubleshooting

### Permission Errors

If you get permission errors for serial ports:

```bash
sudo usermod -aG dialout $USER
# Log out and log back in
```

### Missing Dependencies

If setup script fails, install manually:

```bash
pip install -r requirements.txt
```

### Hardware Not Detected

Check USB devices:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```

Update `rover_config.json` with correct device paths.

---

## 📁 Project Structure

```
v2.10/
├── rover_setup.py              # Setup script (run first)
├── rover_manager.py             # Main manager (start system)
├── rover_config.json            # Configuration file
├── requirements.txt             # Python dependencies
│
├── realsense_vision_server.py   # Vision Server component
├── combo_proximity_bridge.py    # Proximity Bridge component
├── telemetry_dashboard.py       # Dashboard component
├── data_relay.py                # Data Relay component
├── simple_crop_monitor.py       # Crop Monitor component
├── obstacle_navigation.py       # Obstacle Navigation component
│
├── config/
│   └── rover_baseline_v9.param  # ArduPilot parameters
│
└── tools/
    └── apply_params.py          # Parameter tool
```

---

## 🎯 Features

- ✅ Full 360° obstacle detection (LiDAR)
- ✅ RealSense camera for crop monitoring
- ✅ Real-time web dashboard
- ✅ Autonomous obstacle navigation
- ✅ Cloud data relay
- ✅ Automatic component management

---

## 📝 Notes

- All components are managed by `rover_manager.py`
- Components start in the correct order automatically
- Dashboard is available at http://localhost:8081
- Default credentials: admin/admin
- Logs are saved in `logs/` directory

---

## 🔄 Version Information

**Version:** 2.10 (Stable Release)
**Date:** November 2025
**Status:** Production Ready

---

For detailed documentation, see individual component files or contact the development team.

