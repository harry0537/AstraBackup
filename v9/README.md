# Project Astra NZ - V9 🚀

**Autonomous Agricultural Rover System with Vision Server Architecture**

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure hardware
nano rover_config_v9.json

# 3. Start the rover
python3 rover_manager_v9.py
```

**Dashboard**: http://localhost:8081 (user: `admin`, password: `admin`)

---

## 🎯 What's New in V9?

### Major Architectural Change
**V9 introduces a dedicated RealSense Vision Server** to eliminate camera sharing conflicts that plagued V8.

### Key Improvements
✅ **No More Camera Conflicts** - Single owner pattern  
✅ **Better Reliability** - Independent component failures  
✅ **Easier Debugging** - Clear separation of concerns  
✅ **Frame Deduplication** - Metadata prevents duplicate processing  
✅ **Improved Monitoring** - Centralized health status  
✅ **Safe Rollback** - V8 remains intact for emergency fallback  

---

## 📁 Project Structure

```
v9/
├── realsense_vision_server_v9.py   # Component 196: Camera owner
├── combo_proximity_bridge_v9.py    # Component 195: Proximity detection
├── simple_crop_monitor_v9.py       # Component 198: Crop monitoring
├── telemetry_dashboard_v9.py       # Component 194: Web dashboard
├── data_relay_v9.py                # Component 197: Data relay
├── obstacle_navigation_v9.py      # Component 199: Obstacle-based navigation
├── rover_manager_v9.py             # Main startup manager
├── rover_config_v9.json            # Configuration file
├── requirements.txt                # Python dependencies
│
├── start_rover_v9.sh               # Startup script (Linux/Mac)
├── stop_rover_v9.sh                # Stop script (Linux/Mac)
├── check_v9_health.sh              # Health check script
│
├── README.md                       # This file
├── SETUP_GUIDE_V9.md               # Complete setup instructions
├── DETAILED_ARCHITECTURE.md        # Technical architecture
├── IMPLEMENTATION_PLAN.md          # Development roadmap
├── BUG_FIXES_V9.md                 # Bug fixes and review
└── V8_VS_V9_COMPARISON.md          # V8 vs V9 comparison
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────┐
│   RealSense D435i Camera        │
└────────────┬────────────────────┘
             │ SINGLE OWNER
             ▼
┌────────────────────────────────────┐
│  Vision Server (Component 196)     │
│  • RGB Stream @ 15 FPS             │
│  • Depth Stream @ 15 FPS           │
│  • Writes to /tmp/vision_v9/       │
└─────┬──────────────────┬───────────┘
      │ RGB              │ Depth
      ▼                  ▼
┌──────────────┐   ┌──────────────────┐
│ Crop Monitor │   │ Proximity Bridge │
│              │   │ + LiDAR Fusion   │
│              │   │ + MAVLink Output │
└──────┬───────┘   └──────────────────┘
       │
       ▼
┌────────────────────────┐
│ Telemetry Dashboard    │
│ http://localhost:8081  │
└────────────────────────┘
```

---

## 🔧 Components

### Component 196: RealSense Vision Server (NEW!)
**Single owner of RealSense camera**
- Captures RGB @ 15 FPS → `/tmp/vision_v9/rgb_latest.jpg`
- Captures Depth @ 15 FPS → `/tmp/vision_v9/depth_latest.bin`
- Provides frame metadata with sequence numbers
- Health monitoring and auto-recovery

### Component 195: Proximity Bridge (Modified)
**NO CAMERA ACCESS - Reads from Vision Server**
- Reads depth data from files (no camera conflicts!)
- Fuses with LiDAR for 360° coverage
- Sends MAVLink distance_sensor messages @ 10 Hz
- Graceful fallback to LiDAR-only mode

### Component 198: Crop Monitor (Modified)
**Reads RGB from Vision Server**
- Captures crop images every 10 seconds
- Frame deduplication via metadata
- Rolling archive (10 images)
- Dashboard rolling buffer (10 slots)

### Component 194: Telemetry Dashboard
**Web interface for monitoring**
- Live video stream from Vision Server
- Real-time proximity radar
- Crop image gallery
- System health indicators

### Component 197: Data Relay
**Cloud/remote relay**
- Sends telemetry every 2 seconds
- Uploads images every 60 seconds
- Configurable endpoints

### Component 199: Obstacle Navigation (NEW!)
**Reactive navigation without GPS waypoints**
- Reads 8-sector proximity data from proximity bridge
- Finds sector with most clearance
- Steers toward open space
- Adjusts speed based on obstacle proximity
- Stops if obstacles < 1.5m
- Pure reactive navigation - no waypoints needed

---

## 💻 System Requirements

### Hardware
- **Minimum**: Raspberry Pi 4 (4GB RAM)
- **Recommended**: Raspberry Pi 4 (8GB RAM) or Desktop PC
- **Camera**: Intel RealSense D435i
- **LiDAR**: RPLidar S3 (optional but recommended)
- **Flight Controller**: Pixhawk 6C
- **USB**: 3 ports (USB 3.0 for RealSense)

### Software
- **OS**: Ubuntu 20.04+ or Raspberry Pi OS (64-bit) **[ALL CODE RUNS ON UBUNTU]**
- **Python**: 3.8+ (on Ubuntu only)
- **Dependencies**: See `requirements.txt`
- **Dashboard Viewing**: Any device with web browser (Windows, Mac, phone, etc.)

---

## 🚀 Installation

### Quick Install

```bash
# 1. Clone or navigate to v9 directory
cd /path/to/AstraBackup/v9

# 2. Create virtual environment
python3 -m venv ~/rover_venv
source ~/rover_venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify hardware
rs-enumerate-devices  # Should show RealSense
ls /dev/ttyUSB*       # Should show LiDAR
ls /dev/ttyACM*       # Should show Pixhawk

# 5. Configure
nano rover_config_v9.json

# 6. Start
python3 rover_manager_v9.py
```

### Detailed Setup
See **[SETUP_GUIDE_V9.md](SETUP_GUIDE_V9.md)** for complete instructions.

---

## 🎮 Usage

### Obstacle-Based Navigation

**Drive rover using obstacle data without GPS waypoints:**

```bash
# 1. Start proximity bridge first (required)
python3 rover_manager_v9.py
# OR manually:
python3 combo_proximity_bridge_v9.py

# 2. Start obstacle navigation
python3 obstacle_navigation_v9.py
```

**How it works:**
- Reads 8-sector proximity data from `/tmp/proximity_v9.json`
- Finds the sector with most clearance (best direction)
- Steers toward that direction
- Adjusts speed: slows down near obstacles, stops if < 1.5m
- Sends RC override commands to Pixhawk (steering + throttle)
- No GPS waypoints - pure reactive navigation

**Navigation Parameters:**
- Safe distance: 1.5m (stops if closer)
- Caution distance: 3.0m (slows down)
- Update rate: 10Hz
- Steering: ±400 PWM from center
- Throttle: 1400-1600 PWM (slow to moderate speed)

**Safety:**
- Automatically stops if proximity data unavailable
- Stops if obstacles too close
- Sends stop command on shutdown

### Start the System

**Option 1: Rover Manager (Recommended)**
```bash
python3 rover_manager_v9.py
```

**Option 2: Bash Script (Linux/Mac)**
```bash
./start_rover_v9.sh
```

**Option 3: Manual (Debugging)**
```bash
# Terminal 1: Vision Server (MUST START FIRST!)
python3 realsense_vision_server_v9.py

# Terminal 2: Proximity Bridge (wait 5s after Vision Server)
python3 combo_proximity_bridge_v9.py

# Terminal 3: Crop Monitor
python3 simple_crop_monitor_v9.py

# Terminal 4: Dashboard
python3 telemetry_dashboard_v9.py

# Terminal 5: Data Relay (optional)
python3 data_relay_v9.py

# Terminal 6: Obstacle Navigation (optional - for autonomous driving)
python3 obstacle_navigation_v9.py
```

### Stop the System

```bash
# Press Ctrl+C in rover manager

# Or use stop script
./stop_rover_v9.sh

# Or manual
pkill -f _v9.py
```

### Check System Health

```bash
./check_v9_health.sh

# Or watch live
watch -n 5 ./check_v9_health.sh
```

---

## 🔍 Monitoring

### Health Check
```bash
./check_v9_health.sh
```

### Check Individual Components
```bash
# Vision Server
cat /tmp/vision_v9/status.json | python3 -m json.tool

# Proximity Data
cat /tmp/proximity_v9.json | python3 -m json.tool

# Crop Monitor
cat /tmp/crop_monitor_v9.json | python3 -m json.tool
```

### View Logs
```bash
# Vision Server logs
tail -f /tmp/vision_v9/vision_server.log

# Check if files are updating
watch -n 1 "ls -lh /tmp/vision_v9/*.jpg"
```

### Dashboard
**Access**: http://10.244.77.186:8081 (or your configured IP)  
**Login**: `admin` / `admin`

---

## 🐛 Troubleshooting

### Vision Server Won't Start
```bash
# Check if camera is connected
rs-enumerate-devices

# Check if another instance is running
ps aux | grep realsense_vision_server

# Remove stale lock if needed
rm /tmp/vision_v9/.lock
```

### Proximity Bridge in LiDAR-Only Mode
```bash
# Check Vision Server is running
./check_v9_health.sh

# Check depth files exist and are recent
ls -lh /tmp/vision_v9/depth_*
```

### Crop Monitor Not Capturing
```bash
# Check Vision Server RGB files
ls -lh /tmp/vision_v9/rgb_latest.jpg

# Check file age (should be < 1 second old)
stat /tmp/vision_v9/rgb_latest.jpg
```

### Complete Troubleshooting Guide
See **[SETUP_GUIDE_V9.md#troubleshooting](SETUP_GUIDE_V9.md#troubleshooting)**

---

## 🆘 Emergency Rollback to V8

If V9 has critical issues:

```bash
# 1. Stop V9
pkill -f _v9.py

# 2. Restart V8
cd ../v8
python3 rover_manager_v8.py
```

All V8 files remain unchanged for emergency fallback.

---

## 📊 Performance

### Resource Usage (Raspberry Pi 4)
- **CPU**: ~35-40% (all components)
- **RAM**: ~500-600 MB
- **Disk I/O**: ~3-4 MB/s
- **Network**: Variable (dashboard + data relay)

### Frame Rates
- **Vision Server RGB**: 15 FPS
- **Vision Server Depth**: 15 FPS
- **Proximity Updates**: 10 Hz (100ms)
- **Crop Captures**: Every 10 seconds
- **Dashboard Video**: ~15 FPS (streaming)

---

## 📝 Configuration

Edit `rover_config_v9.json`:

```json
{
  "vision_server": {
    "rgb_resolution": [640, 480],
    "fps": 15
  },
  "proximity_bridge": {
    "lidar_port": "/dev/ttyUSB0",
    "pixhawk_port": "/dev/ttyACM0"
  },
  "crop_monitor": {
    "capture_interval_seconds": 10
  },
  "dashboard": {
    "ip": "10.244.77.186",
    "port": 8081
  }
}
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [README.md](README.md) | This file - Quick start guide |
| [SETUP_GUIDE_V9.md](SETUP_GUIDE_V9.md) | Complete setup instructions |
| [DETAILED_ARCHITECTURE.md](DETAILED_ARCHITECTURE.md) | Technical architecture |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Development roadmap |
| [BUG_FIXES_V9.md](BUG_FIXES_V9.md) | Bug fixes and code review |
| [V8_VS_V9_COMPARISON.md](V8_VS_V9_COMPARISON.md) | V8 vs V9 comparison |

---

## 🔐 Security

**Default Credentials**:
- Dashboard: `admin` / `admin`

**⚠️ IMPORTANT**: Change default credentials for production use!

**File Permissions**: All `/tmp/vision_v9/` files are world-readable by default.

---

## 🤝 Contributing

### Reporting Issues
1. Run health check: `./check_v9_health.sh`
2. Collect logs from `/tmp/vision_v9/`
3. Document exact error messages
4. Note hardware configuration

### Testing Changes
1. Test on non-production system first
2. Verify all health checks pass
3. Run for 24+ hours stability test
4. Document performance impact

---

## 📜 License

**Project Astra NZ**  
**Developed by**: Harinder Singh  
**Version**: 9.0  
**Date**: October 2025

---

## 🎯 Next Steps

1. **Read**: [SETUP_GUIDE_V9.md](SETUP_GUIDE_V9.md)
2. **Install**: `pip install -r requirements.txt`
3. **Configure**: Edit `rover_config_v9.json`
4. **Test**: `python3 realsense_vision_server_v9.py`
5. **Deploy**: `python3 rover_manager_v9.py`

---

## ✅ V9 vs V8 Decision Matrix

| Factor | V8 | V9 |
|--------|----|----|
| Camera Conflicts | ❌ Frequent | ✅ None |
| Reliability | ⚠️ Fair | ✅ Excellent |
| Debugging | ❌ Complex | ✅ Simple |
| Recovery | ❌ Manual | ✅ Automatic |
| Maintenance | ❌ Difficult | ✅ Easy |

**Recommendation**: Use V9 for new deployments. Keep V8 as backup.

---

## 📞 Support

For detailed troubleshooting, see:
- [SETUP_GUIDE_V9.md#troubleshooting](SETUP_GUIDE_V9.md#troubleshooting)
- [BUG_FIXES_V9.md](BUG_FIXES_V9.md)

---

**Status**: ✅ Ready for Production  
**Last Updated**: October 31, 2025  
**Version**: 9.0.0

