# V9 Quick Start Guide

## For Someone Who Just Wants It Running

**IMPORTANT**: All Python scripts run on **Ubuntu only** (the rover/robot).  
Dashboard viewing can be done from **any device with a browser** (Windows, Mac, phone).

### Prerequisites (5 minutes - On Ubuntu)
```bash
# On Ubuntu system where rover will run
sudo apt install -y python3-pip python3-venv
python3 -m venv ~/rover_venv
source ~/rover_venv/bin/activate
pip install -r requirements.txt
```

### Configuration (2 minutes)
```bash
# Edit config file
nano rover_config_v9.json

# Change these if needed:
# - lidar_port: Your LiDAR port (default: /dev/ttyUSB0)
# - pixhawk_port: Your Pixhawk port (default: /dev/ttyACM0)
# - dashboard ip: Your dashboard PC IP
```

### Start (30 seconds)
```bash
python3 rover_manager_v9.py
```

### Verify (1 minute)
```bash
# In another terminal:
./check_v9_health.sh

# Should see all green checkmarks
```

### Access Dashboard
**On Ubuntu (local)**:
- http://localhost:8081

**From Windows EC2 or any other device**:
- http://\<ubuntu-ip\>:8081 (replace with Ubuntu system IP)
- Login: `admin` / `admin`
- **No Python needed on Windows** - just open browser!

---

## That's It!

**To stop**: Press `Ctrl+C`

**If something breaks**: 
```bash
pkill -f _v9.py
cd ../v8
python3 rover_manager_v8.py
```

**For detailed help**: See [SETUP_GUIDE_V9.md](SETUP_GUIDE_V9.md)

---

## Common Issues

### "Camera not found"
```bash
rs-enumerate-devices  # Check if RealSense is connected
```

### "LIDAR not found"
```bash
ls /dev/ttyUSB*  # Check if LiDAR is connected
```

### "Permission denied"
```bash
sudo usermod -aG dialout $USER
# Then logout and login again
```

### "Port already in use"
```bash
pkill -f _v9.py  # Stop old instances
```

---

**Done!** 🎉

