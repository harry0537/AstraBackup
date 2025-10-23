# 🚀 Rover-Vision

## Professional Rover Telemetry & Monitoring System

Rover-Vision is a comprehensive rover telemetry and monitoring system designed for autonomous rover operations. It consists of two main components: a **server** that runs on the Ubuntu rover hardware and a **client** for remote monitoring.

## 📦 Package Components

### 🖥️ Server Component (Ubuntu Rover)
- **Location**: `server/` directory
- **Purpose**: Main rover telemetry system
- **Features**: 
  - Real-time sensor data collection
  - Space-optimized image capture
  - Web dashboard interface
  - Hardware integration (LiDAR, Pixhawk, RealSense)
  - Auto-restart and system management

### 💻 Client Component (Windows EC2)
- **Location**: `client/` directory  
- **Purpose**: Remote dashboard viewer
- **Features**:
  - Lightweight dashboard client
  - ZeroTier network integration
  - Minimal system requirements
  - Easy installation and setup

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ROVER-VISION SYSTEM                      │
├─────────────────────────────────────────────────────────────┤
│  🖥️  Ubuntu Rover (Server)    │  💻  Windows EC2 (Client)   │
│  - Hardware integration      │  - Remote dashboard viewer   │
│  - Sensor data collection    │  - ZeroTier network access  │
│  - Web dashboard (port 8081) │  - Minimal installation     │
│  - Auto-restart management   │  - Easy configuration       │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Server Installation (Ubuntu Rover)
```bash
# Download and extract
wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-server.tar.gz
tar -xzf rover-vision-server.tar.gz
cd rover-vision-server

# Install
sudo ./install.sh

# Start system
rover-vision start
```

### Client Installation (Windows EC2)
```bash
# Download and extract
wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-client.zip
unzip rover-vision-client.zip
cd rover-vision-client

# Install
./install.bat

# Start client
rover-vision-client
```

## 📋 Features

### Server Features
- **Modern Dashboard**: Compact single-screen telemetry interface
- **Space Optimization**: Rolling buffer image management (40 images max)
- **Real-time Monitoring**: 1-second refresh rate with live data
- **Hardware Integration**: RPLidar, Pixhawk, RealSense camera support
- **Auto-Restart**: Automatic component recovery and management
- **Virtual Environment**: Isolated Python environment for stability
- **Service Integration**: Optional systemd service for auto-start

### Client Features
- **Remote Access**: Connect to rover dashboard via ZeroTier
- **Lightweight**: Minimal system requirements
- **Easy Setup**: One-click installation and configuration
- **Auto-Connect**: Automatic connection to rover system
- **Status Monitoring**: Real-time connection status
- **Error Handling**: Robust error recovery and reconnection

## 🔧 Installation

### Prerequisites

#### Server (Ubuntu Rover)
- Ubuntu 18.04+ 
- Python 3.7+
- RPLidar, Pixhawk, RealSense camera
- User in dialout group
- Network connectivity

#### Client (Windows EC2)
- Windows 10/11 or Windows Server
- .NET Framework 4.7.2+
- ZeroTier client installed
- Network connectivity

### Installation Steps

1. **Download Package**
   ```bash
   # Server
   wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-server.tar.gz
   
   # Client  
   wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-client.zip
   ```

2. **Install Server**
   ```bash
   tar -xzf rover-vision-server.tar.gz
   cd rover-vision-server
   sudo ./install.sh
   ```

3. **Install Client**
   ```bash
   unzip rover-vision-client.zip
   cd rover-vision-client
   ./install.bat
   ```

4. **Configure Network**
   - Set up ZeroTier network
   - Configure rover IP address
   - Test connectivity

5. **Start System**
   ```bash
   # Server
   rover-vision start
   
   # Client
   rover-vision-client
   ```

## 📖 Usage

### Server Commands
```bash
rover-vision start      # Start the rover system
rover-vision stop       # Stop the rover system
rover-vision restart    # Restart the rover system
rover-vision status     # Show system status
rover-vision logs       # View system logs
rover-vision config     # Edit configuration
rover-vision diagnose   # Run system diagnostics
```

### Client Commands
```bash
rover-vision-client start    # Start the client
rover-vision-client stop     # Stop the client
rover-vision-client config   # Configure connection
rover-vision-client status   # Show connection status
```

## ⚙️ Configuration

### Server Configuration
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

### Client Configuration
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

## 🔧 Troubleshooting

### Server Issues
```bash
# Check system status
rover-vision status

# View logs
rover-vision logs

# Run diagnostics
rover-vision diagnose

# Check hardware
rover-vision check-hardware
```

### Client Issues
```bash
# Check connection
rover-vision-client status

# Test connectivity
rover-vision-client test-connection

# Reset configuration
rover-vision-client reset-config
```

## 📁 Package Structure

```
Rover-Vision/
├── server/                 # Ubuntu rover server
│   ├── install.sh         # Server installer
│   ├── scripts/           # Python scripts
│   ├── config/            # Configuration files
│   └── README.md          # Server documentation
├── client/                # Windows EC2 client
│   ├── install.bat        # Client installer
│   ├── rover-vision-client.exe
│   ├── config/            # Client configuration
│   └── README.md          # Client documentation
├── docs/                  # Documentation
│   ├── installation.md    # Installation guide
│   ├── configuration.md  # Configuration guide
│   └── troubleshooting.md # Troubleshooting guide
├── scripts/               # Utility scripts
│   ├── build-package.sh  # Package builder
│   └── test-system.sh    # System tester
└── README.md              # This file
```

## 🔄 Updates

### Update Server
```bash
rover-vision update
```

### Update Client
```bash
rover-vision-client update
```

## 📞 Support

- **Documentation**: `docs/` directory
- **Server Issues**: Check `server/logs/`
- **Client Issues**: Check Windows Event Log
- **GitHub Issues**: [GitHub Issues](https://github.com/your-repo/rover-vision/issues)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Rover-Vision** - Professional rover telemetry system for autonomous operations.
