#!/bin/bash
"""
Rover-Vision Server Installer
Professional installation script for Ubuntu rover systems
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/rover-vision"
SERVICE_NAME="rover-vision"
USER="rover"
VENV_DIR="$INSTALL_DIR/venv"

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check Ubuntu version
    if ! lsb_release -d | grep -q "Ubuntu"; then
        print_warning "This script is designed for Ubuntu. Other distributions may work but are not tested."
    fi
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 7 ]]; then
        print_error "Python 3.7+ is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "System requirements met"
}

# Install system dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    apt update
    apt install -y \
        python3-venv \
        python3-pip \
        git \
        curl \
        wget \
        systemd \
        udev \
        usbutils \
        v4l-utils
    
    print_success "System dependencies installed"
}

# Create user and groups
setup_user() {
    print_status "Setting up user and permissions..."
    
    # Create rover user if it doesn't exist
    if ! id "$USER" &>/dev/null; then
        useradd -m -s /bin/bash "$USER"
        print_success "Created user: $USER"
    else
        print_status "User $USER already exists"
    fi
    
    # Add user to dialout group
    usermod -aG dialout "$USER"
    usermod -aG video "$USER"
    usermod -aG audio "$USER"
    
    print_success "User permissions configured"
}

# Create installation directory
setup_directories() {
    print_status "Creating installation directories..."
    
    mkdir -p "$INSTALL_DIR"/{bin,config,scripts,logs,data/{images,telemetry},docs}
    chown -R "$USER:$USER" "$INSTALL_DIR"
    
    print_success "Installation directories created"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Create virtual environment
    sudo -u "$USER" python3 -m venv "$VENV_DIR"
    
    # Activate virtual environment and install packages
    sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip
    sudo -u "$USER" "$VENV_DIR/bin/pip" install \
        rplidar-roboticia \
        pymavlink \
        pyrealsense2 \
        opencv-python \
        numpy \
        Pillow \
        requests \
        flask \
        flask-cors
    
    print_success "Python dependencies installed"
}

# Install rover scripts
install_scripts() {
    print_status "Installing rover scripts..."
    
    # Copy Python scripts
    cp scripts/*.py "$INSTALL_DIR/scripts/"
    chmod +x "$INSTALL_DIR/scripts/"*.py
    chown -R "$USER:$USER" "$INSTALL_DIR/scripts"
    
    # Copy configuration files
    cp config/*.json "$INSTALL_DIR/config/"
    chown -R "$USER:$USER" "$INSTALL_DIR/config"
    
    # Copy startup script
    cp scripts/start_rover_system.sh "$INSTALL_DIR/bin/"
    chmod +x "$INSTALL_DIR/bin/start_rover_system.sh"
    chown "$USER:$USER" "$INSTALL_DIR/bin/start_rover_system.sh"
    
    print_success "Rover scripts installed"
}

# Create control script
create_control_script() {
    print_status "Creating control script..."
    
    cat > "$INSTALL_DIR/bin/rover-vision" << 'EOF'
#!/bin/bash
"""
Rover-Vision Control Script
Main control interface for the rover system
"""

INSTALL_DIR="/opt/rover-vision"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON="$VENV_DIR/bin/python3"
MANAGER="$INSTALL_DIR/scripts/rover_manager_v9.py"
CONFIG="$INSTALL_DIR/config/rover_config_v9.json"
SERVICE_NAME="rover-vision"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as rover user
check_user() {
    if [[ "$USER" != "rover" ]]; then
        print_warning "Running as user: $USER (recommended: rover)"
    fi
}

# Start the rover system
start() {
    print_status "Starting Rover-Vision system..."
    check_user
    
    if pgrep -f "rover_manager" > /dev/null; then
        print_warning "Rover system is already running"
        return 1
    fi
    
    # Use the startup script for better port detection
    cd "$INSTALL_DIR"
    if [[ -f "bin/start_rover_system.sh" ]]; then
        print_status "Using startup script with port detection..."
        ./bin/start_rover_system.sh start
    else
        print_status "Using direct startup method..."
        nohup "$PYTHON" "$MANAGER" > logs/rover_manager.out.log 2> logs/rover_manager.err.log &
        echo $! > /tmp/rover-vision.pid
    fi
    
    sleep 3
    if pgrep -f "rover_manager" > /dev/null; then
        print_success "Rover system started"
        print_status "Dashboard: http://0.0.0.0:8081"
        return 0
    else
        print_error "Failed to start rover system"
        return 1
    fi
}

# Stop the rover system
stop() {
    print_status "Stopping Rover-Vision system..."
    
    if [[ -f /tmp/rover-vision.pid ]]; then
        PID=$(cat /tmp/rover-vision.pid)
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm /tmp/rover-vision.pid
        fi
    fi
    
    # Kill any remaining rover processes
    pkill -f "rover_manager" || true
    pkill -f "telemetry_dashboard" || true
    pkill -f "simple_crop_monitor" || true
    pkill -f "combo_proximity_bridge" || true
    
    print_success "Rover system stopped"
}

# Restart the rover system
restart() {
    stop
    sleep 2
    start
}

# Show system status
status() {
    print_status "Rover-Vision System Status"
    echo "================================"
    
    # Check if system is running
    if pgrep -f "rover_manager" > /dev/null; then
        print_success "Rover system: RUNNING"
        
        # Show component status
        echo ""
        echo "Component Status:"
        echo "----------------"
        
        if pgrep -f "telemetry_dashboard" > /dev/null; then
            echo "✓ Telemetry Dashboard: RUNNING"
        else
            echo "✗ Telemetry Dashboard: STOPPED"
        fi
        
        if pgrep -f "simple_crop_monitor" > /dev/null; then
            echo "✓ Crop Monitor: RUNNING"
        else
            echo "✗ Crop Monitor: STOPPED"
        fi
        
        if pgrep -f "combo_proximity_bridge" > /dev/null; then
            echo "✓ Proximity Bridge: RUNNING"
        else
            echo "✗ Proximity Bridge: STOPPED"
        fi
        
        # Show dashboard access
        echo ""
        echo "Dashboard Access:"
        echo "----------------"
        echo "Local:  http://0.0.0.0:8081"
        echo "Network: http://$(hostname -I | awk '{print $1}'):8081"
        
    else
        print_warning "Rover system: STOPPED"
    fi
    
    # Show system resources
    echo ""
    echo "System Resources:"
    echo "-----------------"
    echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
}

# Show logs
logs() {
    print_status "Rover-Vision Logs"
    echo "=================="
    
    if [[ -f "$INSTALL_DIR/logs/rover_manager.out.log" ]]; then
        echo "Recent logs:"
        tail -20 "$INSTALL_DIR/logs/rover_manager.out.log"
    else
        print_warning "No logs found"
    fi
}

# Edit configuration
config() {
    print_status "Opening configuration editor..."
    
    if command -v nano > /dev/null; then
        nano "$CONFIG"
    elif command -v vim > /dev/null; then
        vim "$CONFIG"
    else
        print_error "No text editor found. Please install nano or vim"
        return 1
    fi
}

# Diagnose system
diagnose() {
    print_status "Running system diagnostics..."
    
    echo "Hardware Check:"
    echo "---------------"
    
    # Check LiDAR
    if ls /dev/ttyUSB* > /dev/null 2>&1; then
        echo "✓ LiDAR ports found: $(ls /dev/ttyUSB*)"
    else
        echo "✗ No LiDAR ports found"
    fi
    
    # Check Pixhawk
    if ls /dev/ttyACM* > /dev/null 2>&1; then
        echo "✓ Pixhawk ports found: $(ls /dev/ttyACM*)"
    else
        echo "✗ No Pixhawk ports found"
    fi
    
    # Check RealSense
    if lsusb | grep -q "Intel Corp.*RealSense"; then
        echo "✓ RealSense camera detected"
    else
        echo "✗ RealSense camera not detected"
    fi
    
    # Check permissions
    echo ""
    echo "Permission Check:"
    echo "-----------------"
    if groups | grep -q dialout; then
        echo "✓ User in dialout group"
    else
        echo "✗ User not in dialout group"
    fi
    
    # Check virtual environment
    echo ""
    echo "Environment Check:"
    echo "------------------"
    if [[ -f "$VENV_DIR/bin/python3" ]]; then
        echo "✓ Virtual environment found"
    else
        echo "✗ Virtual environment not found"
    fi
}

# Main command handler
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    config)
        config
        ;;
    diagnose)
        diagnose
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|config|diagnose}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the rover system"
        echo "  stop      - Stop the rover system"
        echo "  restart   - Restart the rover system"
        echo "  status    - Show system status"
        echo "  logs      - Show recent logs"
        echo "  config    - Edit configuration"
        echo "  diagnose  - Run system diagnostics"
        exit 1
        ;;
esac
EOF

    chmod +x "$INSTALL_DIR/bin/rover-vision"
    chown "$USER:$USER" "$INSTALL_DIR/bin/rover-vision"
    
    # Create symlink for easy access
    ln -sf "$INSTALL_DIR/bin/rover-vision" /usr/local/bin/rover-vision
    
    print_success "Control script created"
}

# Create systemd service
create_service() {
    print_status "Creating systemd service..."
    
    cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Rover-Vision Telemetry System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/scripts/rover_manager_v9.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME.service"
    
    print_success "Systemd service created"
}

# Setup udev rules
setup_udev_rules() {
    print_status "Setting up udev rules..."
    
    cat > "/etc/udev/rules.d/99-rover-vision.rules" << 'EOF'
# Rover-Vision Hardware Rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2dae", MODE="0666", SYMLINK+="pixhawk"
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", MODE="0666"
SUBSYSTEM=="video4linux", ATTRS{idVendor}=="8086", MODE="0666"
EOF

    udevadm control --reload-rules
    udevadm trigger
    
    print_success "Udev rules configured"
}

# Main installation function
main() {
    echo "=========================================="
    echo "Rover-Vision Server Installer"
    echo "=========================================="
    echo ""
    
    check_root
    check_requirements
    install_dependencies
    setup_user
    setup_directories
    install_python_deps
    install_scripts
    create_control_script
    create_service
    setup_udev_rules
    
    echo ""
    print_success "Rover-Vision Server installed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Switch to rover user: sudo su - rover"
    echo "2. Start the system: rover-vision start"
    echo "3. Check status: rover-vision status"
    echo "4. Access dashboard: http://0.0.0.0:8081"
    echo ""
    echo "For service management:"
    echo "- Enable auto-start: sudo systemctl enable rover-vision"
    echo "- Start service: sudo systemctl start rover-vision"
    echo "- Check status: sudo systemctl status rover-vision"
}

# Run main function
main "$@"
