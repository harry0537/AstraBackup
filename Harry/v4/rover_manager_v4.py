#!/usr/bin/env python3
"""
Project Astra NZ - Rover Manager V4
Main management script for all rover components with setup integration
"""

import os
import sys
import time
import subprocess
import signal
import json
from datetime import datetime
import threading

# Configuration file
CONFIG_FILE = "rover_config_v4.json"

# Default configuration (used if config file missing)
DEFAULT_CONFIG = {
    "rover_ip": "localhost",
    "dashboard_ip": "10.244.77.186", 
    "dashboard_port": 8081,
    "mavlink_port": 14550,
    "mavproxy_port": 14551,
    "web_port": 5000,
    "component_base_port": 15000
}

# Hardware configuration (NEVER MODIFY)
LIDAR_PORT = '/dev/ttyUSB0'
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600

# Component definitions
COMPONENTS = {
    195: {
        'name': 'Proximity Bridge',
        'script': 'combo_proximity_bridge_v4.py',
        'critical': True,
        'enabled': True
    },
    196: {
        'name': 'Row Following',
        'script': 'row_following_system.py',
        'critical': False,
        'enabled': False
    },
    197: {
        'name': 'Data Relay',
        'script': 'rover_data_relay_v4.py',
        'critical': False,
        'enabled': True
    },
    198: {
        'name': 'Crop Monitor',
        'script': 'crop_monitoring_system.py',
        'critical': False,
        'enabled': False
    }
}

class RoverManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        self.config = self.load_config()
        self.auto_mode = '--auto' in sys.argv
        
    def load_config(self):
        """Load configuration from file or use defaults"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                print(f"✓ Configuration loaded from {CONFIG_FILE}")
                return config
            except Exception as e:
                print(f"⚠️  Error loading config: {e}")
                
        print("⚠️  Using default configuration")
        return DEFAULT_CONFIG
        
    def run_setup(self):
        """Run setup script if needed"""
        print("\n[Pre-Flight] Checking Setup")
        print("-" * 40)
        
        # Check if setup has been run
        if not os.path.exists(CONFIG_FILE):
            print("⚠️  Configuration not found")
            
            if not self.auto_mode:
                response = input("Run setup now? [Y/n]: ")
                if response.lower() != 'n':
                    print("\nRunning setup script...")
                    result = subprocess.run(['python3', 'rover_setup_v4.py'], 
                                          capture_output=False)
                    if result.returncode == 0:
                        print("✓ Setup completed")
                        self.config = self.load_config()
                    else:
                        print("✗ Setup failed")
                        return False
            else:
                print("Auto mode - skipping setup prompt")
        else:
            print("✓ Configuration found")
            
            # Check if IP addresses need updating
            import socket
            try:
                hostname = socket.gethostname()
                current_ip = socket.gethostbyname(hostname)
                if current_ip != self.config.get('rover_ip'):
                    print(f"⚠️  IP address changed: {self.config.get('rover_ip')} → {current_ip}")
                    self.config['rover_ip'] = current_ip
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(self.config, f, indent=2)
                    print("✓ Configuration updated")
            except:
                pass
                
        return True
        
    def print_header(self):
        print("═" * 60)
        print("     PROJECT ASTRA NZ - ROVER MANAGER V4")
        print("═" * 60)
        print(f"Dashboard: http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
        print(f"MAVLink:   UDP port {self.config['mavlink_port']}")
        print("═" * 60)
        
    def check_hardware(self):
        """Phase 1: Hardware validation"""
        print("\n[Phase 1/4] Hardware Validation")
        print("-" * 40)
        
        results = {
            'rplidar': False,
            'pixhawk': False,
            'realsense': False,
            'permissions': False
        }
        
        # Check user permissions
        import grp
        user_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        if 'dialout' in user_groups:
            print("  ✓ User in dialout group")
            results['permissions'] = True
        else:
            print("  ✗ User NOT in dialout group (run setup)")
            
        # Check RPLidar
        if os.path.exists(LIDAR_PORT) or os.path.exists('/dev/rplidar'):
            print(f"  ✓ RPLidar detected")
            results['rplidar'] = True
        else:
            print(f"  ✗ RPLidar not found")
            
        # Check Pixhawk
        if os.path.exists(PIXHAWK_PORT) or os.path.exists('/dev/pixhawk'):
            print(f"  ✓ Pixhawk detected")
            results['pixhawk'] = True
        else:
            # Try alternate detection
            for i in range(10):
                if os.path.exists(f'/dev/ttyACM{i}'):
                    print(f"  ⚠ Pixhawk possibly at /dev/ttyACM{i}")
                    results['pixhawk'] = True
                    break
            if not results['pixhawk']:
                print("  ✗ Pixhawk not detected")
                
        # Check RealSense (non-critical)
        try:
            import pyrealsense2
            print("  ✓ RealSense library available")
            results['realsense'] = True
        except:
            print("  ⚠ RealSense library not found (non-critical)")
            
        # Check network
        try:
            import requests
            response = requests.get(f"http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}/", 
                                   timeout=2)
            print(f"  ✓ Dashboard reachable at {self.config['dashboard_ip']}")
        except:
            print(f"  ⚠ Dashboard not reachable (non-critical)")
            
        # Summary
        critical_ok = results['rplidar'] and results['pixhawk'] and results['permissions']
        
        if critical_ok:
            print("\n✅ Critical hardware ready")
        else:
            print("\n⚠️  Critical hardware issues detected")
            
        if not self.auto_mode:
            response = input("\nContinue with startup? [y/n]: ")
            return response.lower() == 'y'
        else:
            return critical_ok
        
    def select_components(self):
        """Phase 2: Component selection"""
        print("\n[Phase 2/4] Component Selection")
        print("-" * 40)
        
        if self.auto_mode:
            print("Auto mode - using default component selection")
            for comp_id, comp in COMPONENTS.items():
                if comp['enabled']:
                    print(f"  • {comp['name']} ({comp['script']})")
        else:
            for comp_id, comp in COMPONENTS.items():
                default = 'Y' if comp['enabled'] else 'n'
                prompt = f"  Start {comp['name']} ({comp_id})? [{default}/n]: "
                response = input(prompt) or default
                comp['enabled'] = response.lower() != 'n'
                
            # Show summary
            print("\nComponents to start:")
            for comp_id, comp in COMPONENTS.items():
                if comp['enabled']:
                    print(f"  • {comp['name']} ({comp['script']})")
                
    def start_component(self, comp_id, comp_info):
        """Start a single component"""
        if not comp_info['enabled']:
            return False
            
        script_path = comp_info['script']
        if not os.path.exists(script_path):
            print(f"  ✗ Script not found: {script_path}")
            return False
            
        try:
            # Pass configuration to components via environment
            env = os.environ.copy()
            env['ASTRA_CONFIG'] = json.dumps(self.config)
            env['ASTRA_DASHBOARD_IP'] = self.config['dashboard_ip']
            env['ASTRA_DASHBOARD_PORT'] = str(self.config['dashboard_port'])
            env['ASTRA_MAVLINK_PORT'] = str(self.config['mavlink_port'])
            
            process = subprocess.Popen(
                ['python3', script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            self.processes[comp_id] = {
                'process': process,
                'info': comp_info,
                'start_time': datetime.now(),
                'restarts': 0
            }
            return True
        except Exception as e:
            print(f"  ✗ Failed to start {comp_info['name']}: {e}")
            return False
            
    def start_components(self):
        """Phase 3: Start all selected components"""
        print("\n[Phase 3/4] Starting Components")
        print("-" * 40)
        
        for comp_id, comp_info in COMPONENTS.items():
            if comp_info['enabled']:
                print(f"  Starting {comp_info['name']}...", end='')
                if self.start_component(comp_id, comp_info):
                    print(" ✓")
                    time.sleep(2)  # Stagger startup
                else:
                    print(" ✗")
                    if comp_info['critical']:
                        print(f"\n❌ Critical component {comp_info['name']} failed!")
                        return False
        return True
        
    def monitor_components(self):
        """Phase 4: Runtime monitoring"""
        print("\n[Phase 4/4] Runtime Monitor")
        print("-" * 40)
        print("Press Ctrl+C for graceful shutdown\n")
        
        while self.running:
            # Clear screen and show status
            print("\033[H\033[J")  # Clear screen
            print("PROJECT ASTRA NZ - Component Status")
            print("=" * 60)
            print(f"{'Component':<20} {'Status':<12} {'PID':<8} {'Uptime':<15} {'Restarts'}")
            print("-" * 60)
            
            for comp_id, proc_info in self.processes.items():
                comp_name = proc_info['info']['name']
                process = proc_info['process']
                
                if process.poll() is None:
                    status = "✓ RUNNING"
                    pid = str(process.pid)
                    uptime = str(datetime.now() - proc_info['start_time']).split('.')[0]
                else:
                    status = "✗ STOPPED"
                    pid = "-"
                    uptime = "-"
                    
                    # Auto-restart critical components
                    if proc_info['info']['critical'] and proc_info['restarts'] < 3:
                        print(f"\n⚠️  Restarting {comp_name}...")
                        if self.start_component(comp_id, proc_info['info']):
                            proc_info['restarts'] += 1
                            
                restarts = str(proc_info['restarts'])
                print(f"{comp_name:<20} {status:<12} {pid:<8} {uptime:<15} {restarts}")
                
            print("-" * 60)
            print(f"Dashboard: http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
            print(f"MAVLink:   UDP port {self.config['mavlink_port']}")
            print("\nPress Ctrl+C for graceful shutdown")
            
            time.sleep(5)
            
    def shutdown(self):
        """Graceful shutdown of all components"""
        print("\n\nShutting down components...")
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
                    
        print("\n✅ Rover manager shutdown complete")
        
    def run(self):
        """Main execution flow"""
        self.print_header()
        
        # Run setup if needed
        if not self.run_setup():
            print("Setup required before starting")
            return
            
        # Phase 1: Hardware check
        if not self.check_hardware():
            print("Startup cancelled")
            return
            
        # Phase 2: Component selection
        self.select_components()
        
        # Phase 3: Start components
        if not self.start_components():
            print("Failed to start critical components")
            self.shutdown()
            return
            
        # Phase 4: Monitor
        try:
            self.monitor_components()
        except KeyboardInterrupt:
            self.shutdown()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    pass

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    manager = RoverManager()
    manager.run()