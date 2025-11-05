#!/usr/bin/env python3
"""
Project Astra NZ - Rover Manager V9
Manages all V9 components with proper startup order
"""

import subprocess
import time
import os
import sys
import signal
import json
from datetime import datetime

# Component definitions (startup order is CRITICAL in V9)
COMPONENTS = [
    {
        'id': 196,
        'name': 'Vision Server',
        'script': 'realsense_vision_server_v9.py',
        'critical': True,
        'startup_delay': 5,
        'health_check': lambda: os.path.exists('/tmp/vision_v9/status.json')
    },
    {
        'id': 195,
        'name': 'Proximity Bridge',
        'script': 'combo_proximity_bridge_v9.py',
        'critical': True,
        'startup_delay': 2,
        'health_check': lambda: os.path.exists('/tmp/proximity_v9.json')
    },
    {
        'id': 198,
        'name': 'Crop Monitor',
        'script': 'simple_crop_monitor_v9.py',
        'critical': False,
        'startup_delay': 2,
        'health_check': lambda: os.path.exists('/tmp/crop_monitor_v9.json')
    },
    {
        'id': 194,
        'name': 'Dashboard',
        'script': 'telemetry_dashboard_v9.py',
        'critical': False,
        'startup_delay': 2,
        'health_check': None
    },
    {
        'id': 197,
        'name': 'Data Relay',
        'script': 'data_relay_v9.py',
        'critical': False,
        'startup_delay': 0,
        'health_check': None
    }
]


class RoverManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        self.config = self.load_config()
        
        # Detect Python command
        venv_path = os.path.expanduser("~/rover_venv/bin/python3")
        if os.path.exists(venv_path):
            self.python_cmd = venv_path
        else:
            self.python_cmd = "python3"
        
        os.makedirs('logs', exist_ok=True)
    
    def load_config(self):
        """Load or create default configuration"""
        config_file = "rover_config_v9.json"
        default = {
            "dashboard_ip": "0.0.0.0",
            "dashboard_port": 8081,
            "mavlink_port": 14550,
            "lidar_port": "/dev/ttyUSB0",
            "pixhawk_port": "/dev/ttyACM0"
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return {**default, **config}
            except:
                pass
        return default
    
    def setup_directories(self):
        """Create necessary directories."""
        dirs = ['/tmp/vision_v9', '/tmp/crop_archive', '/tmp/rover_vision']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    def start_component(self, component):
        """Start a single component."""
        name = component['name']
        script = component['script']
        
        # Check if already running (cross-platform)
        try:
            # Try Unix pgrep first
            result = subprocess.run(['pgrep', '-f', script], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # pgrep not available (Windows) or timed out - use psutil if available
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and script in ' '.join(cmdline):
                            return None
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except ImportError:
                # psutil not available, skip check
                pass
        except Exception:
            pass
        
        # Start process with log files (like v8)
        try:
            log_name = script.replace('.py', '')
            stdout_file = open(f"logs/{log_name}.out.log", 'a')
            stderr_file = open(f"logs/{log_name}.err.log", 'a')
            
            env = os.environ.copy()
            env['ASTRA_CONFIG'] = json.dumps(self.config)
            
            python_exe = self.python_cmd
            process = subprocess.Popen(
                [python_exe, script],
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait a bit and check if it's still running
            time.sleep(2)
            if process.poll() is None:
                # Store process info with start time and restarts (like v8)
                process_info = {
                    'process': process,
                    'info': component,
                    'start_time': datetime.now(),
                    'restarts': 0,
                    'stdout': stdout_file,
                    'stderr': stderr_file
                }
                
                # Additional startup delay
                if component['startup_delay'] > 0:
                    time.sleep(component['startup_delay'])
                
                # Health check
                if component['health_check']:
                    for _ in range(10):
                        if component['health_check']():
                            break
                        time.sleep(1)
                
                return process_info
            else:
                stdout_file.close()
                stderr_file.close()
                print(f"✗ {name} failed to start")
                return None
        except Exception as e:
            print(f"✗ Failed to start {name}: {e}")
            return None
    
    def monitor(self):
        """Monitor and auto-restart components (like v8)"""
        print("\n[Runtime Monitor]")
        print("=" * 60)
        print("Press Ctrl+C for graceful shutdown\n")
        
        while self.running:
            # Clear screen (like v8)
            try:
                subprocess.run(['clear' if os.name != 'nt' else 'cls'],
                             shell=True, check=False)
            except:
                pass
            
            print("PROJECT ASTRA NZ - Component Status V9")
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
                    
                    # Auto-restart critical components (like v8)
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
                        new_proc_info = self.start_component(proc_info['info'])
                        if new_proc_info:
                            new_proc_info['restarts'] = proc_info['restarts'] + 1
                            self.processes[comp_id] = new_proc_info
                            continue
                
                print(f"{name:<20} {status:<12} {pid:<8} {uptime:<12} {restarts}")
            
            print("-" * 60)
            
            # Show proximity data if available (like v8)
            try:
                with open('/tmp/proximity_v9.json', 'r') as f:
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
    
    def stop_all(self):
        """Graceful shutdown (like v8)"""
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
        """Main execution."""
        print("=" * 60)
        print("PROJECT ASTRA NZ - ROVER MANAGER V9")
        print("=" * 60)
        
        # Setup directories
        self.setup_directories()
        
        # Check if anything is already running (cross-platform)
        try:
            result = subprocess.run(['pgrep', '-f', '_v9.py'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                print("\n⚠ V9 components are already running!")
                print("To stop: ./stop_rover_v9.sh or python3 rover_manager_v9.py --stop")
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # pgrep not available (Windows) - try psutil
            try:
                import psutil
                v9_running = False
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and '_v9.py' in ' '.join(cmdline):
                            v9_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if v9_running:
                    print("\n⚠ V9 components are already running!")
                    print("To stop: python3 rover_manager_v9.py --stop")
                    return False
            except ImportError:
                # psutil not available, continue anyway
                pass
        except Exception:
            pass
        
        # Show which Python executable is being used (like v8)
        venv_path = os.path.expanduser("~/rover_venv/bin/python3")
        if os.path.exists(venv_path):
            print(f"🐍 Using Virtual Environment: {self.python_cmd}")
        else:
            print(f"🐍 Using System Python: {self.python_cmd}")
            print("⚠ WARNING: Virtual environment not found, using system Python")
        
        print(f"Dashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
        print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
        print("=" * 60)
        
        print("\n" + "=" * 60)
        print("STARTING V9 COMPONENTS (in critical order)")
        print("=" * 60)
        
        # Start all components in order
        print("\n[Starting Components]")
        print("-" * 40)
        failed_critical = False
        for component in COMPONENTS:
            print(f"  Starting {component['name']}...", end='')
            process_info = self.start_component(component)
            
            if process_info:
                self.processes[component['id']] = process_info
                print(" ✓")
                time.sleep(2)
            else:
                print(" ✗")
                if component['critical']:
                    print(f"\n✗ Critical component failed!")
                    failed_critical = True
                    break
        
        if failed_critical:
            self.shutdown()
            return False
        
        # Monitor (like v8)
        try:
            self.monitor()
        except KeyboardInterrupt:
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Alias for stop_all for consistency"""
        self.stop_all()


def main():
    # Check if running from correct directory
    if not os.path.exists('realsense_vision_server_v9.py'):
        print("ERROR: Must run from v9 directory")
        print("Run: cd /path/to/v9 && python3 rover_manager_v9.py")
        return 1
    
    manager = RoverManager()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        manager.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    success = manager.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

