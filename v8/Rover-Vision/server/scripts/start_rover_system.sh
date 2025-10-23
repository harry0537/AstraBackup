#!/bin/bash
"""
Rover-Vision System Startup Script
Automatically detects ports and starts the rover system
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
VENV_DIR="$INSTALL_DIR/venv"
PYTHON="$VENV_DIR/bin/python3"
SCRIPTS_DIR="$INSTALL_DIR/scripts"
CONFIG_DIR="$INSTALL_DIR/config"

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

# Check if running as rover user
check_user() {
    if [[ "$USER" != "rover" ]]; then
        print_warning "Running as user: $USER (recommended: rover)"
        print_status "Consider switching to rover user: sudo su - rover"
    fi
}

# Run port detection
detect_ports() {
    print_status "Running port detection..."
    
    cd "$SCRIPTS_DIR"
    
    if [[ -f "port_detector.py" ]]; then
        print_status "Running automatic port detection..."
        $PYTHON port_detector.py
        
        if [[ $? -eq 0 ]]; then
            print_success "Port detection completed"
        else
            print_warning "Port detection had issues, continuing with existing configuration"
        fi
    else
        print_warning "Port detector not found, using existing configuration"
    fi
}

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check if virtual environment exists
    if [[ ! -f "$PYTHON" ]]; then
        print_error "Virtual environment not found at $VENV_DIR"
        print_status "Please run the installer first: sudo ./install.sh"
        exit 1
    fi
    
    # Check if scripts exist
    if [[ ! -f "$SCRIPTS_DIR/rover_manager_v9.py" ]]; then
        print_error "Rover manager script not found"
        exit 1
    fi
    
    # Check if config exists
    if [[ ! -f "$CONFIG_DIR/rover_config_v9.json" ]]; then
        print_warning "Configuration file not found, using defaults"
    fi
    
    print_success "System requirements met"
}

# Start the rover system
start_rover() {
    print_status "Starting Rover-Vision system..."
    
    cd "$INSTALL_DIR"
    
    # Start the rover manager
    nohup $PYTHON "$SCRIPTS_DIR/rover_manager_v9.py" > logs/rover_manager.out.log 2> logs/rover_manager.err.log &
    echo $! > /tmp/rover-vision.pid
    
    sleep 3
    
    # Check if system started successfully
    if pgrep -f "rover_manager" > /dev/null; then
        print_success "Rover system started successfully"
        print_status "Dashboard: http://0.0.0.0:8081"
        print_status "Logs: $INSTALL_DIR/logs/"
        return 0
    else
        print_error "Failed to start rover system"
        print_status "Check logs: $INSTALL_DIR/logs/rover_manager.err.log"
        return 1
    fi
}

# Show system status
show_status() {
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

# Main function
main() {
    echo "=========================================="
    echo "Rover-Vision System Startup"
    echo "=========================================="
    echo ""
    
    check_user
    check_requirements
    detect_ports
    
    # Check if system is already running
    if pgrep -f "rover_manager" > /dev/null; then
        print_warning "Rover system is already running"
        show_status
        exit 0
    fi
    
    # Start the system
    if start_rover; then
        echo ""
        show_status
        echo ""
        print_success "Rover-Vision system started successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Access dashboard: http://0.0.0.0:8081"
        echo "2. Check status: rover-vision status"
        echo "3. View logs: rover-vision logs"
    else
        print_error "Failed to start Rover-Vision system"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-start}" in
    start)
        main
        ;;
    status)
        show_status
        ;;
    detect)
        detect_ports
        ;;
    *)
        echo "Usage: $0 {start|status|detect}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the rover system (default)"
        echo "  status    - Show system status"
        echo "  detect    - Run port detection only"
        exit 1
        ;;
esac
