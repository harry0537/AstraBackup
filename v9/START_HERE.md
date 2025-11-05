# 🚀 START HERE - Project Astra NZ V9

**Welcome to the V9 system!** This guide will get you up and running quickly.

---

## ⚡ Quick Access Links

### 🎯 For Ubuntu Deployment
**Start here** → [`QUICK_START.md`](QUICK_START.md) (10-minute setup)

### 🖥️ For Windows EC2 Viewing
**Start here** → [`ZEROTIER_SETUP.md`](ZEROTIER_SETUP.md) (Access dashboard)

### 📚 For Understanding Everything
**Start here** → [`FINAL_SUMMARY.md`](FINAL_SUMMARY.md) (Complete overview)

---

## 🎯 What You Need to Know

### Where Does Code Run?
- ✅ **Ubuntu Only** - All Python scripts run on Ubuntu rover/robot
- ✅ **Windows EC2** - Just web browser access (no Python needed)
- ✅ **ZeroTier Network** - Connects Ubuntu and Windows securely

### Network Setup (Already Configured!)
- **ZeroTier Network ID**: `4753cf475f287023`
- **Ubuntu Rover IP**: `172.25.77.186` (ZeroTier virtual IP)
- **Dashboard URL**: `http://172.25.77.186:8081`
- **Login**: `admin` / `admin`

---

## 🚀 Super Quick Start

### On Ubuntu Rover (5 minutes)
```bash
# 1. Navigate to v9 directory
cd /path/to/AstraBackup/v9

# 2. Create virtual environment (if not done)
python3 -m venv ~/rover_venv
source ~/rover_venv/bin/activate

# 3. Install dependencies (first time only)
pip install -r requirements.txt

# 4. Start everything!
python3 rover_manager_v9.py
```

### On Windows EC2 (30 seconds)
```
1. Open Chrome/Firefox/Edge
2. Go to: http://172.25.77.186:8081
3. Login: admin / admin
4. Done! You're monitoring the rover!
```

---

## 📁 Key Files You Need

### To Run The System
1. **`rover_manager_v9.py`** - Start all components
2. **`check_v9_health.sh`** - Check system health
3. **`rover_config_v9.json`** - Configuration (edit if needed)

### To Learn The System
1. **`README.md`** - Project overview
2. **`QUICK_START.md`** - Fast Ubuntu setup
3. **`ZEROTIER_SETUP.md`** - Windows EC2 access
4. **`FINAL_SUMMARY.md`** - Complete summary

### For Troubleshooting
1. **`SETUP_GUIDE_V9.md`** - Detailed setup & troubleshooting
2. **`BUGS_FOUND_AND_FIXED.md`** - Known issues & fixes
3. **`INDEX.md`** - Complete file index

---

## 🎯 What's New in V9?

### ⭐ #1: Camera Sharing FIXED!
**Problem**: Multiple scripts fighting over RealSense camera  
**Solution**: New Vision Server owns camera, others read from files  
**Benefit**: No more camera conflicts!

### ⭐ #2: Single Owner Pattern
**New Component**: `realsense_vision_server_v9.py` (Component 196)  
**What It Does**: Exclusively controls RealSense camera  
**Outputs**: RGB images + depth data to `/tmp/vision_v9/`

### ⭐ #3: Other Scripts Updated
- **Proximity Bridge**: Reads depth from Vision Server (no direct camera)
- **Crop Monitor**: Reads RGB from Vision Server (with deduplication)
- **Dashboard**: Streams video from Vision Server files

### ⭐ #4: Bug Fixes
**5 bugs fixed**:
1. Windows compatibility (fcntl)
2. JSON parsing errors
3. Array bounds checking
4. Percentile calculation errors
5. Cross-platform process checking

### ⭐ #5: Better Documentation
**12 comprehensive guides** covering:
- Setup & deployment
- ZeroTier network access
- Technical architecture
- Bug fixes & QA
- Complete project summary

---

## 🌐 System Architecture (Simple View)

```
┌────────────────────────────────────────┐
│  UBUNTU ROVER                          │
│  (172.25.77.186 via ZeroTier)          │
│  ────────────────────────────────────  │
│                                         │
│  Vision Server ─────┐                  │
│  (Owns Camera)      │                  │
│                     │                  │
│                     ├──→ Proximity     │
│                     ├──→ Crop Monitor  │
│                     └──→ Dashboard     │
│                                         │
│  Dashboard: http://0.0.0.0:8081        │
└─────────────┬───────────────────────────┘
              │
              │ ZeroTier Network
              │ (Encrypted)
              │
      ┌───────▼──────────┐
      │  Windows EC2     │
      │  ──────────────  │
      │  Web Browser     │
      │  :8081           │
      └──────────────────┘
```

---

## ✅ Pre-Flight Checklist

### Before Starting (Ubuntu)
- [ ] Ubuntu 20.04+ LTS installed
- [ ] Python 3.8+ available
- [ ] RealSense D435i camera connected (USB 3.0)
- [ ] RPLidar S3 connected (optional)
- [ ] Pixhawk connected (optional)
- [ ] User in `dialout` group: `sudo usermod -aG dialout $USER`
- [ ] Logged out and back in (for group changes)

### Network (ZeroTier)
- [ ] ZeroTier installed on Ubuntu
- [ ] Joined network: `4753cf475f287023`
- [ ] ZeroTier shows "OK" status
- [ ] Can ping rover from Windows EC2

### Ready to Run!
- [ ] `cd /path/to/v9`
- [ ] `source ~/rover_venv/bin/activate`
- [ ] `pip install -r requirements.txt`
- [ ] `python3 rover_manager_v9.py`

---

## 🆘 Common Issues

### "Vision Server won't start"
```bash
# Remove lock file and retry
rm -f /tmp/vision_v9/.lock
python3 rover_manager_v9.py
```

### "Permission denied on serial ports"
```bash
# Add user to dialout group
sudo usermod -aG dialout $USER
# MUST logout and login for changes!
```

### "Can't access dashboard from Windows"
```bash
# On Ubuntu - check firewall
sudo ufw allow 8081/tcp
sudo ufw allow from 172.25.0.0/16

# Check ZeroTier connection
sudo zerotier-cli listnetworks
# Should show "OK" for network 4753cf475f287023
```

### "Camera not found"
```bash
# Test camera
rs-enumerate-devices

# If not found, try different USB port (USB 3.0 required)
```

---

## 📚 Documentation Roadmap

### I'm New Here
1. Read **this file** (you are here!)
2. Read [`README.md`](README.md) - Overview
3. Follow [`QUICK_START.md`](QUICK_START.md) - Setup

### I Want to Run It
1. Follow [`QUICK_START.md`](QUICK_START.md) - Ubuntu setup
2. Read [`ZEROTIER_SETUP.md`](ZEROTIER_SETUP.md) - Windows access
3. Use [`check_v9_health.sh`](check_v9_health.sh) - Verify health

### I Want to Understand It
1. Read [`FINAL_SUMMARY.md`](FINAL_SUMMARY.md) - Complete overview
2. Study [`DETAILED_ARCHITECTURE.md`](DETAILED_ARCHITECTURE.md) - Technical
3. Review [`V8_VS_V9_COMPARISON.md`](V8_VS_V9_COMPARISON.md) - What changed

### I'm Having Problems
1. Check [`SETUP_GUIDE_V9.md`](SETUP_GUIDE_V9.md) - Troubleshooting
2. Review [`BUGS_FOUND_AND_FIXED.md`](BUGS_FOUND_AND_FIXED.md) - Known issues
3. See emergency fixes above

### I Want Everything
1. Read [`INDEX.md`](INDEX.md) - Complete file index
2. Read [`FINAL_SUMMARY.md`](FINAL_SUMMARY.md) - Project summary
3. Explore all 12 documentation files

---

## 🎯 Success Criteria

### After Starting System
You should see:
- ✅ 7 processes running (`ps aux | grep _v9.py`)
- ✅ Vision Server started first
- ✅ All health checks green (`./check_v9_health.sh`)
- ✅ Dashboard accessible locally (`http://localhost:8081`)
- ✅ Dashboard accessible from Windows EC2 (`http://172.25.77.186:8081`)

### Dashboard Should Show
- ✅ Live video stream (from RealSense)
- ✅ Proximity data updating (LiDAR + depth)
- ✅ Telemetry data (if Pixhawk connected)
- ✅ All components showing "RUNNING" status
- ✅ No error messages

---

## 🎉 You're Ready!

**Choose your path**:

### Path 1: I Just Want It Running
→ [`QUICK_START.md`](QUICK_START.md)

### Path 2: I'm Viewing From Windows EC2
→ [`ZEROTIER_SETUP.md`](ZEROTIER_SETUP.md)

### Path 3: I Want to Understand Everything
→ [`FINAL_SUMMARY.md`](FINAL_SUMMARY.md)

### Path 4: I Need Complete Setup Guide
→ [`SETUP_GUIDE_V9.md`](SETUP_GUIDE_V9.md)

---

## 📊 Project Stats

- **Total Files**: 25
- **Python Scripts**: 7
- **Documentation**: 12 comprehensive guides
- **Lines of Code**: ~3,500
- **Lines of Docs**: ~4,200
- **Bugs Fixed**: 5
- **Status**: ✅ Production Ready

---

## 🎖️ Key Features

✅ Single camera owner (Vision Server)  
✅ No camera conflicts  
✅ Frame deduplication  
✅ Atomic file operations  
✅ Process locking  
✅ Comprehensive error handling  
✅ ZeroTier remote access  
✅ Ubuntu-only deployment (simpler)  
✅ Windows EC2 viewing (browser only)  
✅ Rollback to V8 (if needed)  
✅ Health monitoring  
✅ 12 documentation guides  

---

**Version**: 9.0.0  
**Platform**: Ubuntu 20.04+ LTS  
**Remote Access**: ZeroTier (4753cf475f287023)  
**Status**: ✅ PRODUCTION READY  
**Last Updated**: October 31, 2024

---

*Welcome to Project Astra NZ V9! 🚀*

*Choose your path above and let's get started!*

