# 🚀 Rover-Vision Deployment Guide

## 📋 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ROVER-VISION DEPLOYMENT                  │
├─────────────────────────────────────────────────────────────┤
│  💻  Development System    │  🖥️  Ubuntu Rover    │  ☁️  AWS EC2    │
│  - Windows 10/11          │  - Ubuntu 18.04+     │  - Windows Server │
│  - Development tools       │  - Hardware sensors   │  - ZeroTier client │
│  - Git repository          │  - Rover-Vision Server│  - Dashboard client │
│  - Remote access (PuTTY)   │  - Port detection     │  - Network access   │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Deployment Overview

### System Roles

1. **Development System** (Your current machine)
   - Package development and testing
   - Remote access to rover via PuTTY
   - Git repository management

2. **Ubuntu Rover System** (Target deployment)
   - Hardware sensors (LiDAR, Pixhawk, RealSense)
   - Rover-Vision server components
   - Port detection and auto-reconnection
   - Web dashboard (port 8081)

3. **AWS EC2 Windows Machine** (Dashboard access)
   - ZeroTier network client
   - Rover-Vision client application
   - Remote dashboard viewing
   - Network connectivity to rover

## 📦 Package Structure

```
Rover-Vision/
├── server/                    # Ubuntu rover deployment
│   ├── install.sh           # Server installer
│   ├── scripts/              # Python components
│   │   ├── rover_manager_v9.py
│   │   ├── telemetry_dashboard_v9.py
│   │   ├── simple_crop_monitor_v9.py
│   │   ├── combo_proximity_bridge_v9.py
│   │   ├── port_detector.py
│   │   └── start_rover_system.sh
│   ├── config/
│   │   └── rover_config_v9.json
│   └── README.md
├── client/                    # Windows EC2 deployment
│   ├── install.bat          # Client installer
│   ├── rover-vision-client.exe
│   └── README.md
├── docs/                      # Documentation
│   └── port-detection.md
└── README.md                  # Main documentation
```

## 🚀 Deployment Steps

### Step 1: Prepare Development System

```bash
# On your development machine
cd D:\AstraBackup\v8\Rover-Vision

# Verify package structure
dir server\scripts\
dir client\
dir docs\

# Check file permissions (will be set on Ubuntu)
```

### Step 2: Deploy to Ubuntu Rover

#### Via PuTTY/SSH:
```bash
# Connect to rover via PuTTY
ssh rover@ROVER_IP

# Create deployment directory
mkdir -p ~/rover-vision-deploy
cd ~/rover-vision-deploy

# Transfer files from development system
# (Use SCP, SFTP, or copy via development machine)
```

#### Transfer Methods:

**Option A: Direct Copy (if files are accessible)**
```bash
# From development machine, copy to rover
scp -r Rover-Vision/* rover@ROVER_IP:~/rover-vision-deploy/
```

**Option B: Git Clone (if repository is available)**
```bash
# On rover system
git clone https://github.com/your-repo/rover-vision.git
cd rover-vision
```

**Option C: Manual Transfer**
```bash
# Copy files manually via PuTTY file transfer
# or use WinSCP, FileZilla, etc.
```

#### Install on Rover:
```bash
# On rover system
cd ~/rover-vision-deploy/server

# Make installer executable
chmod +x install.sh

# Run installer (requires sudo)
sudo ./install.sh

# Switch to rover user
sudo su - rover

# Start the system
rover-vision start

# Check status
rover-vision status
```

### Step 3: Deploy to AWS EC2

#### On EC2 Windows Machine:
```cmd
# Create deployment directory
mkdir C:\rover-vision-deploy
cd C:\rover-vision-deploy

# Copy client files
# (Transfer from development system)

# Install client
install.bat

# Configure connection
rover-vision-client config

# Start client
rover-vision-client start
```

## 🔧 Configuration

### Rover System Configuration

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
  "network": {
    "zerotier_enabled": true,
    "zerotier_network": "YOUR_NETWORK_ID"
  }
}
```

### EC2 Client Configuration

```json
{
  "server": {
    "ip": "ROVER_ZEROTIER_IP",
    "port": 8081
  },
  "network": {
    "zerotier_enabled": true,
    "auto_reconnect": true
  }
}
```

## 🌐 Network Setup

### ZeroTier Configuration

1. **Create ZeroTier Network**
   - Sign up at zerotier.com
   - Create new network
   - Note network ID

2. **Install ZeroTier on Rover**
   ```bash
   # Install ZeroTier
   curl -s https://install.zerotier.com | sudo bash
   
   # Join network
   sudo zerotier-cli join YOUR_NETWORK_ID
   
   # Check status
   zerotier-cli status
   ```

3. **Install ZeroTier on EC2**
   ```cmd
   # Download and install ZeroTier client
   # Join same network
   zerotier-cli join YOUR_NETWORK_ID
   ```

4. **Authorize Devices**
   - Go to ZeroTier web interface
   - Authorize both rover and EC2 devices
   - Note IP addresses assigned

## 🔍 Verification Steps

### 1. Verify Rover System
```bash
# On rover system
rover-vision status

# Check components
ps aux | grep rover

# Test dashboard locally
curl http://localhost:8081

# Check port detection
python3 /opt/rover-vision/scripts/port_detector.py
```

### 2. Verify Network Connectivity
```bash
# From rover to EC2
ping EC2_ZEROTIER_IP

# From EC2 to rover
ping ROVER_ZEROTIER_IP

# Test port connectivity
telnet ROVER_ZEROTIER_IP 8081
```

### 3. Verify Client Connection
```cmd
# On EC2
rover-vision-client status

# Test connection
rover-vision-client test

# Open dashboard
# Should show rover telemetry data
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Port Detection Failures
```bash
# On rover system
rover-vision diagnose

# Manual port detection
python3 /opt/rover-vision/scripts/port_detector.py --verbose

# Check hardware connections
lsusb
ls /dev/tty*
```

#### 2. Network Connectivity Issues
```bash
# Check ZeroTier status
zerotier-cli status

# Check network configuration
zerotier-cli listnetworks

# Restart ZeroTier
sudo systemctl restart zerotier-one
```

#### 3. Client Connection Issues
```cmd
# On EC2
rover-vision-client test

# Check firewall
netsh advfirewall firewall show rule name="Rover-Vision"

# Reset configuration
rover-vision-client reset
```

## 📊 Monitoring

### Rover System Monitoring
```bash
# Check system status
rover-vision status

# View logs
rover-vision logs

# Monitor resources
htop
df -h
```

### Network Monitoring
```bash
# Check ZeroTier status
zerotier-cli status

# Monitor network traffic
iftop

# Check port connectivity
netstat -tlnp | grep 8081
```

### Client Monitoring
```cmd
# Check client status
rover-vision-client status

# View client logs
type %APPDATA%\Rover-Vision\logs\client.log
```

## 🔄 Updates and Maintenance

### Updating Rover System
```bash
# On rover system
rover-vision stop

# Update files
# (Transfer new versions from development)

# Restart system
rover-vision start
```

### Updating Client
```cmd
# On EC2
rover-vision-client stop

# Update files
# (Transfer new versions from development)

# Restart client
rover-vision-client start
```

## 📞 Support

### Log Locations
- **Rover Logs**: `/opt/rover-vision/logs/`
- **Client Logs**: `%APPDATA%\Rover-Vision\logs\`
- **System Logs**: `/var/log/syslog` (rover)

### Debug Commands
```bash
# Rover system debug
rover-vision diagnose
journalctl -u rover-vision -f

# Network debug
zerotier-cli status -j
```

---

**Rover-Vision Deployment Guide** - Complete deployment for 3-system architecture.
