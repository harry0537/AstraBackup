#!/usr/bin/env python3
"""
Project Astra NZ - Rover Manager V9
Modern rover management with v9 components and enhanced monitoring
Simplified component management with auto-restart and space optimization

FUNCTIONALITY:
- Manages and monitors all rover components with auto-restart capability
- Provides enhanced system monitoring with CPU, memory, and disk usage
- Automatically uses virtual environment Python for all components
- Handles graceful shutdown and cleanup of all processes
- Displays real-time component status and system statistics
- Monitors proximity data and crop monitor storage information

COMPONENT MANAGEMENT:
- Proximity Bridge (195): Critical - LiDAR and RealSense sensor fusion
- Data Relay (197): Optional - Data transmission component
- Crop Monitor (198): Optional - Space-optimized image capture
- Telemetry Dashboard (199): Optional - Web interface on port 8081

ENHANCED FEATURES:
- Virtual environment auto-detection and usage
- System resource monitoring (CPU, memory, disk)
- Enhanced logging with timestamps and component tracking
- Automatic restart of failed critical components
- Real-time status display with uptime and restart counts
- Storage monitoring for crop monitor component

USAGE:
- Run: python3 rover_manager_v9.py
- Optional: python3 rover_manager_v9.py --auto (for service mode)
- Automatically starts all enabled components
- Press Ctrl+C for graceful shutdown
"""

import os
import sys
import time
import subprocess
import signal
import json
from datetime import datetime

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

CONFIG_FILE = "rover_config_v9.json"  # Main configuration file

# ============================================================================
# COMPONENT DEFINITIONS FOR V9
# ============================================================================
# Each component has a unique ID, name, script file, and configuration
# Critical components are automatically restarted if they fail
# Non-critical components are optional and can be disabled

COMPONENTS = {
    195: {
        'name': 'Proximity Bridge',           # Main sensor fusion component
        'script': 'combo_proximity_bridge_v9.py',
        'critical': True,                     # Critical - auto-restart on failure
        'enabled': True                       # Enabled by default
    },
    197: {
        'name': 'Data Relay',                 # Data transmission component
        'script': 'data_relay_v9.py',
        'critical': False,                    # Optional - not auto-restarted
        'enabled': True
    },
    198: {
        'name': 'Crop Monitor',               # Space-optimized image capture
        'script': 'simple_crop_monitor_v9.py',
        'critical': False,                    # Optional - not auto-restarted
        'enabled': True
    },
    199: {
        'name': 'Telemetry Dashboard',        # Web interface
        'script': 'telemetry_dashboard_v9.py',
        'critical': False,                    # Optional - not auto-restarted
        'enabled': True
    }
}

# ============================================================================
# ROVER MANAGER CLASS
# ============================================================================

class RoverManager:
    """
    Enhanced rover management system for V9 components
    
    This class handles:
    - Starting and stopping all rover components
    - Monitoring component health and status
    - Automatic restart of failed critical components
    - System resource monitoring (CPU, memory, disk)
    - Virtual environment detection and usage
    - Enhanced logging with timestamps
    - Graceful shutdown and cleanup
    """
    
    def __init__(self):
        """
        Initialize the rover manager with configuration and setup
        
        Sets up:
        - Component process tracking
        - Configuration loading
        - Auto-mode detection
        - Log directory creation
        """
        self.processes = {}          # Dictionary to track component processes
        self.running = True          # Main loop control flag
        self.config = self.load_config()  # Load configuration from file
        self.auto_mode = '--auto' in sys.argv  # Check for auto-mode flag
        os.makedirs('logs', exist_ok=True)  # Create logs directory

    def load_config(self):
        """Load or create default configuration"""
        default = {
            "dashboard_ip": "0.0.0.0",
            "dashboard_port": 8081,
            "mavlink_port": 14550,
            "rover_ip": "172.25.77.186",
            "lidar_port": "/dev/ttyUSB0",
            "pixhawk_port": "/dev/ttyACM0",
            "realsense_config": {
                "width": 640,
                "height": 480,
                "fps": 15
            },
            "crop_monitor": {
                "interval": 60,
                "max_images": 40,
                "quality": 60
            }
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    for key, value in default.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                print(f"[WARNING] Config file error: {e}, using defaults")
        return default

    def check_hardware(self):
        """Enhanced hardware validation"""
        print("\n[Hardware Check]")
        print("-" * 40)

        checks = {
            'lidar': os.path.exists(self.config.get('lidar_port', '/dev/ttyUSB0')),
            'pixhawk': os.path.exists(self.config.get('pixhawk_port', '/dev/ttyACM0')),
            'permissions': 'dialout' in str(subprocess.run(['groups'],
                                           capture_output=True).stdout),
            'storage': self.check_storage_space()
        }

        for name, ok in checks.items():
            status = "✓" if ok else "✗"
            print(f"  {status} {name.title()}")

        if all(checks.values()):
            print("\n✓ Hardware ready")
            return True
        else:
            print("\n⚠ Hardware issues detected")
            if self.auto_mode:
                return False
            return input("Continue anyway? [y/N]: ").lower() == 'y'

    def check_storage_space(self):
        """Check available storage space"""
        try:
            # Check /tmp directory space
            result = subprocess.run(['df', '/tmp'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        available = int(parts[3])  # Available in KB
                        available_mb = available / 1024
                        if available_mb > 100:  # Need at least 100MB
                            return True
            return False
        except:
            return False

    def start_component(self, comp_id, comp_info):
        """Start a single component with enhanced error handling and virtual environment support"""
        if not comp_info['enabled'] or not os.path.exists(comp_info['script']):
            return False

        try:
            env = os.environ.copy()
            env['ASTRA_CONFIG'] = json.dumps(self.config)
            env['ASTRA_VERSION'] = 'v9'

            log_name = comp_info['script'].replace('.py', '')
            stdout = open(f"logs/{log_name}.out.log", 'a')
            stderr = open(f"logs/{log_name}.err.log", 'a')

            # Add timestamp to log files
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stdout.write(f"\n=== {comp_info['name']} started at {timestamp} ===\n")
            stdout.flush()

            # Determine Python executable - prefer virtual environment
            python_executable = sys.executable
            venv_python = os.path.expanduser("~/rover_venv/bin/python3")
            
            if os.path.exists(venv_python):
                python_executable = venv_python
                print(f"  [INFO] Using virtual environment Python: {python_executable}")
            else:
                print(f"  [WARNING] Virtual environment not found, using system Python: {python_executable}")

            process = subprocess.Popen(
                [python_executable, comp_info['script']],
                stdout=stdout,
                stderr=stderr,
                env=env
            )

            self.processes[comp_id] = {
                'process': process,
                'info': comp_info,
                'start_time': datetime.now(),
                'restarts': 0,
                'stdout': stdout,
                'stderr': stderr,
                'last_restart': None
            }
            return True
        except Exception as e:
            print(f"  ✗ Failed to start {comp_info['name']}: {e}")
            return False

    def get_system_stats(self):
        """Get system statistics for monitoring"""
        try:
            # Get CPU usage
            cpu_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
            cpu_usage = "N/A"
            if cpu_result.returncode == 0:
                lines = cpu_result.stdout.split('\n')
                for line in lines:
                    if 'Cpu(s)' in line:
                        parts = line.split(',')
                        if len(parts) > 0:
                            cpu_usage = parts[0].split()[1]
                        break

            # Get memory usage
            mem_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
            mem_usage = "N/A"
            if mem_result.returncode == 0:
                lines = mem_result.stdout.split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        used = int(parts[2])
                        total = int(parts[1])
                        mem_usage = f"{used}/{total}MB"

            # Get disk usage
            disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
            disk_usage = "N/A"
            if disk_result.returncode == 0:
                lines = disk_result.stdout.split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        disk_usage = f"{parts[2]}/{parts[1]} ({parts[4]})"

            return {
                'cpu': cpu_usage,
                'memory': mem_usage,
                'disk': disk_usage
            }
        except:
            return {'cpu': 'N/A', 'memory': 'N/A', 'disk': 'N/A'}

    def monitor(self):
        """Enhanced monitoring with system stats"""
        print("\n[Runtime Monitor]")
        print("=" * 80)
        print("Press Ctrl+C for graceful shutdown\n")

        while self.running:
            try:
                subprocess.run(['clear' if os.name != 'nt' else 'cls'],
                             shell=True, check=False)
            except:
                pass

            print("PROJECT ASTRA NZ - Component Status V9")
            print("=" * 80)
            print(f"{'Component':<20} {'Status':<12} {'PID':<8} {'Uptime':<12} {'Restarts':<8} {'Last Restart'}")
            print("-" * 80)

            for comp_id, proc_info in self.processes.items():
                name = proc_info['info']['name']
                process = proc_info['process']

                if process.poll() is None:
                    status = "✓ RUNNING"
                    pid = str(process.pid)
                    uptime = str(datetime.now() - proc_info['start_time']).split('.')[0]
                    restarts = str(proc_info['restarts'])
                    last_restart = proc_info.get('last_restart', '-')
                else:
                    status = "✗ STOPPED"
                    pid = uptime = "-"
                    restarts = str(proc_info['restarts'])
                    last_restart = proc_info.get('last_restart', '-')

                    # Auto-restart critical components
                    if proc_info['info']['critical'] and proc_info['restarts'] < 3:
                        print(f"\n⚠ Restarting {name}...")

                        # Close old log files before restarting
                        for handle in ['stdout', 'stderr']:
                            if handle in proc_info:
                                try:
                                    proc_info[handle].close()
                                except:
                                    pass

                        # Start new component instance
                        if self.start_component(comp_id, proc_info['info']):
                            self.processes[comp_id]['restarts'] = proc_info['restarts'] + 1
                            self.processes[comp_id]['last_restart'] = datetime.now().strftime('%H:%M:%S')

                print(f"{name:<20} {status:<12} {pid:<8} {uptime:<12} {restarts:<8} {last_restart}")

            print("-" * 80)

            # Show system statistics
            stats = self.get_system_stats()
            print(f"System: CPU {stats['cpu']} | Memory {stats['memory']} | Disk {stats['disk']}")

            # Show proximity data if available
            try:
                with open('/tmp/proximity_v8.json', 'r') as f:
                    prox = json.load(f)
                sectors = prox.get('sectors_cm', [])
                min_cm = prox.get('min_cm', 0)
                tx = prox.get('messages_sent', 0)
                age = time.time() - prox.get('timestamp', time.time())

                if sectors:
                    print(f"\nProximity: {' '.join(f'{int(x):4d}' for x in sectors)} cm")
                    print(f"Closest: {min_cm}cm | Age: {age:.1f}s | TX: {tx}")
            except:
                pass

            # Show crop monitor status if available
            try:
                with open('/tmp/crop_monitor_v9.json', 'r') as f:
                    crop = json.load(f)
                storage_info = crop.get('storage_info', {})
                print(f"Crop Monitor: {crop.get('capture_count', 0)} images, {storage_info.get('total_size_mb', 0):.1f}MB total")
            except:
                pass

            print(f"\nDashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
            print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
            print("Press Ctrl+C for graceful shutdown")

            time.sleep(5)

    def shutdown(self):
        """Graceful shutdown with cleanup"""
        print("\n\nShutting down...")
        self.running = False

        for comp_id, proc_info in self.processes.items():
            process = proc_info['process']
            if process.poll() is None:
                print(f"  Stopping {proc_info['info']['name']}...", end='')
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(" ✓")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print(" (forced)")

            # Close log files
            for handle in ['stdout', 'stderr']:
                if handle in proc_info:
                    try:
                        proc_info[handle].close()
                    except:
                        pass

        print("\n✓ Shutdown complete")

    def run(self):
        """
        Main execution method with enhanced startup and monitoring
        
        This method:
        1. Displays startup information and configuration
        2. Performs hardware checks and validation
        3. Starts all enabled components in sequence
        4. Enters monitoring loop for component health
        5. Handles graceful shutdown on interruption
        
        The monitoring loop continuously:
        - Checks component status and health
        - Displays real-time system statistics
        - Shows proximity data and storage information
        - Automatically restarts failed critical components
        - Provides dashboard access information
        """
        print("=" * 80)
        print("PROJECT ASTRA NZ - ROVER MANAGER V9")
        print("=" * 80)
        print(f"Dashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
        print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
        print(f"MAVLink Port: {self.config.get('mavlink_port', 14550)}")
        print("=" * 80)

        # Perform hardware validation before starting components
        if not self.check_hardware():
            print("Startup cancelled")
            return

        # Start all enabled components in sequence
        print("\n[Starting Components]")
        print("-" * 40)
        for comp_id, comp_info in COMPONENTS.items():
            if comp_info['enabled']:
                print(f"  Starting {comp_info['name']}...", end='')
                if self.start_component(comp_id, comp_info):
                    print(" ✓")
                    time.sleep(2)  # Brief delay between component starts
                else:
                    print(" ✗")
                    # If critical component fails, shutdown entire system
                    if comp_info['critical']:
                        print(f"\n✗ Critical component failed!")
                        self.shutdown()
                        return

        # Enter main monitoring loop
        try:
            self.monitor()
        except KeyboardInterrupt:
            self.shutdown()

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    pass

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    manager = RoverManager()
    manager.run()
