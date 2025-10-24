#!/usr/bin/env python3
"""
Project Astra NZ - Rover Manager V8
Simplified component management with auto-restart - Bug Fixes from V7
"""

import os
import sys
import time
import subprocess
import signal
import json
from datetime import datetime

CONFIG_FILE = "rover_config_v8.json"

# Virtual environment configuration
VENV_PATH = os.path.expanduser("~/rover_venv")
VENV_PYTHON = os.path.join(VENV_PATH, "bin", "python3")

def get_python_executable():
    """Get the correct Python executable (venv if available, system otherwise)"""
    if os.path.exists(VENV_PYTHON):
        return VENV_PYTHON
    else:
        return sys.executable

# Component definitions (only stable components enabled by default)
COMPONENTS = {
    195: {
        'name': 'Proximity Bridge',
        'script': 'combo_proximity_bridge_v8.py',
        'critical': True,
        'enabled': True
    },
    197: {
        'name': 'Data Relay',
        'script': 'data_relay_v8.py',
        'critical': False,
        'enabled': True
    },
    198: {
        'name': 'Crop Monitor (5s Updates)',
        'script': 'simple_crop_monitor_v8.py',
        'critical': False,
        'enabled': True
    },
    200: {
        'name': 'Telemetry Dashboard',
        'script': 'telemetry_dashboard_v8.py',
        'critical': False,
        'enabled': True
    }
}

class RoverManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        self.config = self.load_config()
        self.auto_mode = '--auto' in sys.argv
        os.makedirs('logs', exist_ok=True)

    def load_config(self):
        """Load or create default configuration"""
        default = {
            "dashboard_ip": "0.0.0.0",
            "dashboard_port": 8081,
            "mavlink_port": 14550
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default

    def load_hardware_config(self):
        """Load hardware configuration from config file"""
        default_hardware = {
            'lidar_port': '/dev/ttyUSB0',
            'pixhawk_port': '/dev/ttyACM0',
            'realsense_config': {'width': 424, 'height': 240, 'fps': 15}
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Ensure we always return valid values
                    lidar_port = config.get('lidar_port')
                    pixhawk_port = config.get('pixhawk_port')
                    
                    return {
                        'lidar_port': lidar_port if lidar_port else default_hardware['lidar_port'],
                        'pixhawk_port': pixhawk_port if pixhawk_port else default_hardware['pixhawk_port'],
                        'realsense_config': config.get('realsense_config', default_hardware['realsense_config'])
                    }
            except Exception as e:
                print(f"[WARNING] Failed to load config: {e}, using defaults")
        return default_hardware

    def check_hardware(self):
        """Quick hardware validation"""
        print("\n[Hardware Check]")
        print("-" * 40)

        # Load hardware configuration
        hardware_config = self.load_hardware_config()

        checks = {
            'lidar': os.path.exists(hardware_config.get('lidar_port', '/dev/ttyUSB0')),
            'pixhawk': os.path.exists(hardware_config.get('pixhawk_port', '/dev/ttyACM0')),
            'permissions': 'dialout' in str(subprocess.run(['groups'],
                                           capture_output=True).stdout)
        }

        for name, ok in checks.items():
            print(f"  {'✓' if ok else '✗'} {name.title()}")

        if all(checks.values()):
            print("\n✓ Hardware ready")
            return True
        else:
            print("\n⚠ Hardware issues detected")
            if self.auto_mode:
                return False
            return input("Continue anyway? [y/N]: ").lower() == 'y'

    def start_component(self, comp_id, comp_info):
        """Start a single component"""
        if not comp_info['enabled'] or not os.path.exists(comp_info['script']):
            print(f"  ⚠ Skipping {comp_info['name']}: {'disabled' if not comp_info['enabled'] else 'script not found'}")
            return False

        try:
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            
            env = os.environ.copy()
            env['ASTRA_CONFIG'] = json.dumps(self.config)

            log_name = comp_info['script'].replace('.py', '')
            stdout = open(f"logs/{log_name}.out.log", 'a')
            stderr = open(f"logs/{log_name}.err.log", 'a')

            python_exe = get_python_executable()
            print(f"  → Starting {comp_info['name']} with {python_exe}")
            
            process = subprocess.Popen(
                [python_exe, comp_info['script']],
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
                'stderr': stderr
            }
            print(f"  ✓ {comp_info['name']} started (PID: {process.pid})")
            return True
        except Exception as e:
            print(f"  ✗ Failed to start {comp_info['name']}: {e}")
            return False

    def monitor(self):
        """Monitor and auto-restart components"""
        print("\n[Runtime Monitor]")
        print("=" * 60)
        print("Press Ctrl+C for graceful shutdown\n")

        while self.running:
            # FIX BUG #13: Use subprocess instead of os.system
            try:
                subprocess.run(['clear' if os.name != 'nt' else 'cls'],
                             shell=True, check=False)
            except:
                pass  # If clear/cls fails, continue anyway

            print("PROJECT ASTRA NZ - Component Status V8")
            print("=" * 60)
            print(f"{'Component':<20} {'Status':<12} {'PID':<8} {'Uptime':<12} {'Restarts'}")
            print("-" * 60)

            for comp_id, proc_info in self.processes.items():
                name = proc_info['info']['name']
                process = proc_info['process']

                if process.poll() is None:
                    status = "✓ RUNNING"
                    pid = str(process.pid)
                    uptime = str(datetime.now() - proc_info['start_time']).split('.')[0]
                    restarts = str(proc_info['restarts'])
                else:
                    status = "✗ STOPPED"
                    pid = uptime = "-"
                    restarts = str(proc_info['restarts'])

                    # FIX BUG #1: Auto-restart critical components - properly increment counter
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
                            # FIX: Properly increment restart counter in the dictionary
                            self.processes[comp_id]['restarts'] = proc_info['restarts'] + 1

                print(f"{name:<20} {status:<12} {pid:<8} {uptime:<12} {restarts}")

            print("-" * 60)

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

            print(f"\nDashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
            print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
            print("Press Ctrl+C for graceful shutdown")

            time.sleep(5)

    def shutdown(self):
        """Graceful shutdown"""
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

            # FIX BUG #7: Always close log files on shutdown
            for handle in ['stdout', 'stderr']:
                if handle in proc_info:
                    try:
                        proc_info[handle].close()
                    except:
                        pass

        print("\n✓ Shutdown complete")

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("PROJECT ASTRA NZ - ROVER MANAGER V8")
        print("=" * 60)
        
        # Show which Python executable is being used
        python_exe = get_python_executable()
        if python_exe == VENV_PYTHON:
            print(f"🐍 Using Virtual Environment: {python_exe}")
        else:
            print(f"🐍 Using System Python: {python_exe}")
            print("⚠ WARNING: Virtual environment not found, using system Python")
        
        print(f"Dashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
        print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
        print("=" * 60)

        if not self.check_hardware():
            print("Startup cancelled")
            return

        # Start enabled components
        print("\n[Starting Components]")
        print("-" * 40)
        for comp_id, comp_info in COMPONENTS.items():
            if comp_info['enabled']:
                print(f"  Starting {comp_info['name']}...", end='')
                if self.start_component(comp_id, comp_info):
                    print(" ✓")
                    time.sleep(2)
                else:
                    print(" ✗")
                    if comp_info['critical']:
                        print(f"\n✗ Critical component failed!")
                        self.shutdown()
                        return

        # Monitor
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
