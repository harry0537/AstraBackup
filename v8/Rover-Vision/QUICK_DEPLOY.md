# 🚀 Quick Deployment Checklist

## 📋 Pre-Deployment Checklist

### ✅ Development System (Your Machine)
- [ ] Rover-Vision package created in `D:\AstraBackup\v8\Rover-Vision\`
- [ ] All server scripts present (`server/scripts/`)
- [ ] All client files present (`client/`)
- [ ] Documentation complete (`docs/`)
- [ ] PuTTY configured for rover access

### ✅ Ubuntu Rover System
- [ ] Ubuntu 18.04+ installed
- [ ] User `rover` created and in `dialout` group
- [ ] Hardware connected (LiDAR, Pixhawk, RealSense)
- [ ] Network connectivity confirmed
- [ ] PuTTY access working

### ✅ AWS EC2 Windows Machine
- [ ] Windows Server/10 installed
- [ ] Network connectivity confirmed
- [ ] Remote access configured

## 🚀 Quick Deployment Steps

### 1. Transfer to Rover (via PuTTY)
```bash
# Connect to rover
ssh rover@ROVER_IP

# Create directory
mkdir -p ~/rover-vision
cd ~/rover-vision

# Transfer files (use SCP, SFTP, or manual copy)
# From your development machine:
scp -r D:\AstraBackup\v8\Rover-Vision\server\* rover@ROVER_IP:~/rover-vision/
```

### 2. Install on Rover
```bash
# On rover system
cd ~/rover-vision
sudo ./install.sh

# Switch to rover user
sudo su - rover

# Start system
rover-vision start

# Check status
rover-vision status
```

### 3. Transfer to EC2
```cmd
# Copy client files to EC2
# (Use RDP, file transfer, etc.)

# Install client
install.bat

# Configure and start
rover-vision-client config
rover-vision-client start
```

## 🔧 Quick Configuration

### Rover Config
```bash
# Edit rover configuration
sudo nano /opt/rover-vision/config/rover_config_v9.json

# Key settings:
# - dashboard.ip: "0.0.0.0"
# - dashboard.port: 8081
# - hardware.lidar_port: "/dev/ttyUSB0"
# - hardware.pixhawk_port: "/dev/ttyACM0"
```

### EC2 Client Config
```json
{
  "server": {
    "ip": "ROVER_ZEROTIER_IP",
    "port": 8081
  }
}
```

## 🌐 Network Setup (Quick)

### ZeroTier Setup
1. **Create ZeroTier account** at zerotier.com
2. **Create network** and note network ID
3. **Install on rover**: `curl -s https://install.zerotier.com | sudo bash`
4. **Join network**: `sudo zerotier-cli join NETWORK_ID`
5. **Install on EC2** and join same network
6. **Authorize devices** in ZeroTier web interface

## ✅ Verification

### Rover System
```bash
# Check status
rover-vision status

# Test dashboard
curl http://localhost:8081

# Check hardware
rover-vision diagnose
```

### Network
```bash
# From rover
ping EC2_ZEROTIER_IP

# From EC2
ping ROVER_ZEROTIER_IP
```

### Client
```cmd
# Check status
rover-vision-client status

# Test connection
rover-vision-client test
```

## 🚨 Common Issues & Quick Fixes

### Port Detection Issues
```bash
# Manual port detection
python3 /opt/rover-vision/scripts/port_detector.py

# Check hardware
lsusb
ls /dev/tty*
```

### Network Issues
```bash
# Restart ZeroTier
sudo systemctl restart zerotier-one

# Check status
zerotier-cli status
```

### Client Issues
```cmd
# Reset client
rover-vision-client reset

# Check firewall
netsh advfirewall firewall show rule name="Rover-Vision"
```

## 📞 Quick Support

### Log Locations
- **Rover**: `/opt/rover-vision/logs/`
- **Client**: `%APPDATA%\Rover-Vision\logs\`

### Debug Commands
```bash
# Rover debug
rover-vision diagnose
rover-vision logs

# Client debug
rover-vision-client status
```

---

**Quick Deployment** - Fast track to Rover-Vision deployment.
