# Rover-Vision Client

## 💻 Remote Dashboard Viewer

Rover-Vision Client is a lightweight Windows application that connects to the Rover-Vision server via ZeroTier network for remote monitoring of rover operations.

## 🚀 Features

- **Remote Access**: Connect to rover dashboard via ZeroTier network
- **Lightweight**: Minimal system requirements and resource usage
- **Auto-Connect**: Automatic connection to rover system
- **Status Monitoring**: Real-time connection status and health
- **Error Handling**: Robust error recovery and reconnection
- **Easy Setup**: One-click installation and configuration
- **ZeroTier Integration**: Seamless network connectivity

## 📋 System Requirements

- **Operating System**: Windows 10/11 or Windows Server 2016+
- **.NET Framework**: 4.7.2 or higher
- **ZeroTier**: ZeroTier client installed and configured
- **Network**: Internet connectivity for ZeroTier
- **Memory**: 100MB RAM minimum
- **Disk Space**: 50MB available space

## 🚀 Quick Installation

### Prerequisites
1. **Install ZeroTier Client**
   - Download from [ZeroTier.com](https://www.zerotier.com/download/)
   - Install and join your ZeroTier network
   - Note your ZeroTier IP address

2. **Get Rover IP**
   - Contact rover operator for ZeroTier IP address
   - Default port: 8081

### Install Client
```bash
# Download client package
wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-client.zip

# Extract package
unzip rover-vision-client.zip
cd rover-vision-client

# Run installer
install.bat
```

### Start Client
```bash
# Start the client
rover-vision-client.exe

# Or use command line
rover-vision-client start
```

## 📖 Usage

### Basic Commands
```bash
rover-vision-client start      # Start the client
rover-vision-client stop       # Stop the client
rover-vision-client restart    # Restart the client
rover-vision-client status     # Show connection status
rover-vision-client config     # Configure connection settings
rover-vision-client test       # Test connection to rover
```

### Configuration
```bash
# Edit configuration
rover-vision-client config

# Test connection
rover-vision-client test

# Show status
rover-vision-client status
```

## ⚙️ Configuration

### Configuration File
Location: `%APPDATA%\Rover-Vision\config.json`

```json
{
  "server": {
    "ip": "ROVER_ZEROTIER_IP",
    "port": 8081,
    "timeout": 30
  },
  "network": {
    "zerotier_enabled": true,
    "auto_reconnect": true,
    "reconnect_interval": 5
  },
  "dashboard": {
    "auto_refresh": true,
    "refresh_interval": 1000,
    "fullscreen": false
  }
}
```

### ZeroTier Configuration
1. **Join Network**
   - Open ZeroTier client
   - Join rover network (get network ID from rover operator)
   - Wait for connection (green status)

2. **Get Rover IP**
   - Check ZeroTier client for rover IP address
   - Usually starts with `10.147.x.x` or similar
   - Update configuration with rover IP

3. **Test Connection**
   ```bash
   rover-vision-client test
   ```

## 🔧 Troubleshooting

### Connection Issues
```bash
# Check ZeroTier status
zerotier-cli status

# Test network connectivity
ping ROVER_ZEROTIER_IP

# Check client status
rover-vision-client status
```

### Common Problems

#### 1. ZeroTier Not Connected
**Problem**: "ZeroTier not connected"
**Solution**:
```bash
# Check ZeroTier service
sc query ZeroTierOne

# Restart ZeroTier service
sc stop ZeroTierOne
sc start ZeroTierOne

# Join network again
zerotier-cli join NETWORK_ID
```

#### 2. Cannot Connect to Rover
**Problem**: "Connection refused"
**Solution**:
```bash
# Test connectivity
ping ROVER_ZEROTIER_IP
telnet ROVER_ZEROTIER_IP 8081

# Check firewall
netsh advfirewall firewall show rule name="Rover-Vision"

# Update configuration
rover-vision-client config
```

#### 3. Dashboard Not Loading
**Problem**: "Dashboard not loading"
**Solution**:
```bash
# Check browser
rover-vision-client test

# Clear cache
rover-vision-client clear-cache

# Restart client
rover-vision-client restart
```

### Debug Mode
```bash
# Enable debug logging
rover-vision-client --debug

# View logs
rover-vision-client logs

# Reset configuration
rover-vision-client reset
```

## 📁 File Structure

```
Rover-Vision-Client/
├── rover-vision-client.exe    # Main client executable
├── install.bat                # Installation script
├── uninstall.bat              # Uninstallation script
├── config/                    # Configuration files
│   ├── default.json          # Default configuration
│   └── config.json           # User configuration
├── logs/                      # Log files
│   ├── client.log            # Client logs
│   └── error.log             # Error logs
└── README.md                  # This file
```

## 🔄 Updates

### Update Client
```bash
rover-vision-client update
```

### Manual Update
```bash
# Download latest version
wget https://github.com/your-repo/rover-vision/releases/latest/download/rover-vision-client.zip

# Extract and replace
unzip rover-vision-client.zip
copy rover-vision-client.exe .
```

## 📞 Support

- **Logs**: Check `%APPDATA%\Rover-Vision\logs\`
- **Configuration**: Check `%APPDATA%\Rover-Vision\config.json`
- **ZeroTier**: Check ZeroTier client status
- **Network**: Test connectivity to rover IP
- **Issues**: GitHub Issues

## 🎯 Features Summary

### Connection Management
- **Auto-Connect**: Automatically connects to rover on startup
- **Reconnection**: Automatic reconnection on connection loss
- **Status Monitoring**: Real-time connection status display
- **Error Recovery**: Robust error handling and recovery

### Dashboard Features
- **Remote Access**: Full access to rover dashboard
- **Real-time Data**: Live telemetry data updates
- **Image Streaming**: Live rover vision feed
- **Proximity Radar**: Interactive obstacle visualization
- **System Status**: Component health and performance

### Network Integration
- **ZeroTier Support**: Seamless ZeroTier network integration
- **Firewall Friendly**: Works through firewalls and NAT
- **Secure Connection**: Encrypted ZeroTier tunnel
- **Auto-Discovery**: Automatic rover discovery (optional)

---

**Rover-Vision Client** - Lightweight remote monitoring for rover operations.
