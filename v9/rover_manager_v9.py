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
        'startup_delay': 3,  # Start AFTER Vision Server, BEFORE Data Relay
        'health_check': lambda: os.path.exists('/tmp/proximity_v9.json')
    },
    {
        'id': 197,
        'name': 'Data Relay',
        'script': 'data_relay_v9.py',
        'critical': False,
        'startup_delay': 2,  # Start AFTER Proximity Bridge (so it can still read telemetry)
        'health_check': None
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
    
    def cleanup_orphaned_processes(self):
        """Kill any orphaned V9 processes before starting new ones."""
        print("\n[Cleanup] Checking for orphaned V9 processes...")
        
        # Get current PID to avoid killing ourselves
        current_pid = os.getpid()
        
        # List of V9 scripts to check for (excluding manager - we'll handle it separately)
        v9_scripts = [
            'realsense_vision_server_v9.py',
            'combo_proximity_bridge_v9.py',
            'simple_crop_monitor_v9.py',
            'telemetry_dashboard_v9.py',
            'data_relay_v9.py'
        ]
        
        killed_count = 0
        
        # First, kill old manager processes (but not this one)
        try:
            # Get all rover_manager_v9.py PIDs
            result = subprocess.run(
                ['pgrep', '-f', 'rover_manager_v9.py'],
                capture_output=True,
                timeout=2,
                text=True
            )
            if result.returncode == 0:
                pids = [int(p.strip()) for p in result.stdout.strip().split('\n') if p.strip()]
                for pid in pids:
                    if pid != current_pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                            killed_count += 1
                        except:
                            pass
                if killed_count > 0:
                    print(f"  ✓ Sent SIGTERM to {killed_count} old manager process(es)")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass
        
        # Kill all other _v9.py processes gracefully (excluding manager)
        try:
            # Use pgrep to get PIDs, then kill each one except current
            result = subprocess.run(
                ['pgrep', '-f', '_v9.py'],
                capture_output=True,
                timeout=2,
                text=True
            )
            if result.returncode == 0:
                pids = [int(p.strip()) for p in result.stdout.strip().split('\n') if p.strip()]
                killed_this_round = 0
                for pid in pids:
                    if pid != current_pid:
                        try:
                            os.kill(pid, signal.SIGTERM)
                            killed_this_round += 1
                        except:
                            pass
                if killed_this_round > 0:
                    killed_count += killed_this_round
                    print(f"  ✓ Sent SIGTERM to {killed_this_round} orphaned V9 process(es)")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            # Fallback: use pkill (will also kill current process, but we'll restart anyway)
            try:
                result = subprocess.run(
                    ['pkill', '-f', '_v9.py'],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    killed_count += 1
                    print("  ✓ Sent SIGTERM to _v9.py processes")
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                pass
        
        # Wait a moment for graceful shutdown
        if killed_count > 0:
            time.sleep(2)
            
            # Force kill any remaining processes (excluding current)
            try:
                result = subprocess.run(
                    ['pgrep', '-f', '_v9.py'],
                    capture_output=True,
                    timeout=2,
                    text=True
                )
                if result.returncode == 0:
                    pids = [int(p.strip()) for p in result.stdout.strip().split('\n') if p.strip()]
                    force_killed = 0
                    for pid in pids:
                        if pid != current_pid:
                            try:
                                os.kill(pid, signal.SIGKILL)
                                force_killed += 1
                            except:
                                pass
                    if force_killed > 0:
                        print(f"  ✓ Force killed {force_killed} remaining V9 process(es)")
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                # Fallback: use pkill -9
                try:
                    subprocess.run(['pkill', '-9', '-f', '_v9.py'], capture_output=True, timeout=2)
                except:
                    pass
        
        # Verify cleanup using ps/grep
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                timeout=2,
                text=True
            )
            if result.returncode == 0:
                v9_processes = [line for line in result.stdout.split('\n') if '_v9.py' in line and 'grep' not in line]
                if v9_processes:
                    print(f"  ⚠ Warning: {len(v9_processes)} V9 process(es) still running:")
                    for proc in v9_processes[:3]:  # Show first 3
                        print(f"    {proc[:80]}")
                else:
                    print("  ✓ No orphaned V9 processes found")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            # Fallback: try using pgrep
            try:
                result = subprocess.run(
                    ['pgrep', '-f', '_v9.py'],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    pids = result.stdout.decode().strip().split('\n')
                    pids = [p for p in pids if p]
                    if pids:
                        print(f"  ⚠ Warning: Found {len(pids)} V9 process(es) (PIDs: {', '.join(pids[:5])})")
                    else:
                        print("  ✓ No orphaned V9 processes found")
                else:
                    print("  ✓ No orphaned V9 processes found")
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                print("  ⚠ Could not verify cleanup (ps/pgrep not available)")
        
        print()
    
    def setup_directories(self):
        """Create necessary directories."""
        dirs = ['/tmp/vision_v9', '/tmp/crop_archive', '/tmp/rover_vision']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    def start_component(self, component):
        """Start a single component (like v8 format)."""
        name = component['name']
        script = component['script']
        
        if not os.path.exists(script):
            return False
        
        # Start process with log files (like v8)
        try:
            log_name = script.replace('.py', '')
            stdout_file = open(f"logs/{log_name}.out.log", 'a')
            stderr_file = open(f"logs/{log_name}.err.log", 'a')
            
            env = os.environ.copy()
            env['ASTRA_CONFIG'] = json.dumps(self.config)
            
            python_exe = self.python_cmd
            print(f"  → Starting {name} with {python_exe}")
            
            process = subprocess.Popen(
                [python_exe, script],
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Store process info with start time and restarts (like v8)
            process_info = {
                'process': process,
                'info': component,
                'start_time': datetime.now(),
                'restarts': 0,
                'stdout': stdout_file,
                'stderr': stderr_file
            }
            
            # Wait a bit and check if it's still running
            time.sleep(2)
            if process.poll() is None:
                print(f"  ✓ {name} started (PID: {process.pid})")
                
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
                print(f"  ✗ Failed to start {name}")
                return False
        except Exception as e:
            print(f"  ✗ Failed to start {name}: {e}")
            return False
    
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
                    
                    # Check if all values are max (no detections)
                    valid_detections = sum(1 for s in sectors if s < 2500)
                    if valid_detections == 0:
                        print(f"  ⚠ No obstacle detections (all at max 2500cm)")
                    else:
                        print(f"  ✓ {valid_detections}/8 sectors detecting obstacles")
            except:
                pass
            
            print(f"\nDashboard (Local): http://{self.config['dashboard_ip']}:{self.config['dashboard_port']}")
            print(f"Dashboard (Network): http://{self.config.get('rover_ip', 'ROVER_IP')}:{self.config['dashboard_port']}")
            print("Press Ctrl+C for graceful shutdown")
            
            time.sleep(5)
    
    def stop_all(self):
        """Graceful shutdown (like v8) - stop managed processes and kill any orphans"""
        print("\n\nShutting down...")
        self.running = False
        
        # First, gracefully stop all managed processes
        for comp_id, proc_info in self.processes.items():
            process = proc_info['process']
            if process.poll() is None:
                print(f"  Stopping {proc_info['info']['name']}...", end='')
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print(" ✓")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print(" (forced)")
                except:
                    print(" (error)")
            
            # Close log files
            for handle in ['stdout', 'stderr']:
                if handle in proc_info:
                    try:
                        proc_info[handle].close()
                    except:
                        pass
        
        # Then kill any remaining orphaned V9 processes (like LIDAR that might keep spinning)
        print("  Cleaning up orphaned processes...", end='')
        try:
            # Graceful kill first
            subprocess.run(['pkill', '-f', '_v9.py'], capture_output=True, timeout=2)
            time.sleep(1)
            # Force kill if still running
            result = subprocess.run(['pkill', '-9', '-f', '_v9.py'], capture_output=True, timeout=2)
            if result.returncode == 0:
                print(" ✓")
            else:
                print(" (none found)")
        except:
            print(" (error)")
        
        print("\n✓ Shutdown complete")
    
    def run(self):
        """Main execution."""
        print("=" * 60)
        print("PROJECT ASTRA NZ - ROVER MANAGER V9")
        print("=" * 60)
        
        # Cleanup orphaned processes FIRST (before starting anything)
        self.cleanup_orphaned_processes()
        
        # Setup directories
        self.setup_directories()
        
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
        
        # Start all components in order (like v8)
        print("\n[Starting Components]")
        print("-" * 40)
        failed_critical = False
        for component in COMPONENTS:
            process_info = self.start_component(component)
            
            if process_info:
                self.processes[component['id']] = process_info
                time.sleep(2)
            else:
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
        """Graceful shutdown - stop all managed processes and kill orphans"""
        self.stop_all()
        # Also clean up any orphaned processes that might have been spawned
        try:
            subprocess.run(['pkill', '-f', '_v9.py'], capture_output=True, timeout=2)
            time.sleep(1)
            subprocess.run(['pkill', '-9', '-f', '_v9.py'], capture_output=True, timeout=2)
        except:
            pass


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

