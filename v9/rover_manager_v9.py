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
        
        # Detect Python command
        venv_path = os.path.expanduser("~/rover_venv/bin/python3")
        if os.path.exists(venv_path):
            self.python_cmd = venv_path
            print("✓ Using virtual environment")
        else:
            self.python_cmd = "python3"
            print("⚠ Using system Python")
    
    def setup_directories(self):
        """Create necessary directories."""
        print("\nSetting up directories...")
        dirs = ['/tmp/vision_v9', '/tmp/crop_archive', '/tmp/rover_vision']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        print("✓ Directories ready")
    
    def start_component(self, component):
        """Start a single component."""
        name = component['name']
        script = component['script']
        
        print(f"\nStarting {name}...")
        
        # Check if already running (cross-platform)
        try:
            # Try Unix pgrep first
            result = subprocess.run(['pgrep', '-f', script], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                print(f"⚠ {name} is already running")
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # pgrep not available (Windows) or timed out - use psutil if available
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and script in ' '.join(cmdline):
                            print(f"⚠ {name} is already running (PID: {proc.info['pid']})")
                            return None
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except ImportError:
                # psutil not available, skip check
                pass
        except Exception:
            pass
        
        # Start process
        try:
            process = subprocess.Popen(
                [self.python_cmd, script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait a bit and check if it's still running
            time.sleep(2)
            if process.poll() is None:
                print(f"✓ {name} started (PID: {process.pid})")
                
                # Additional startup delay
                if component['startup_delay'] > 0:
                    print(f"  Waiting {component['startup_delay']}s for initialization...")
                    time.sleep(component['startup_delay'])
                
                # Health check
                if component['health_check']:
                    for _ in range(10):
                        if component['health_check']():
                            print(f"  ✓ {name} health check passed")
                            break
                        time.sleep(1)
                
                return process
            else:
                stdout, stderr = process.communicate()
                print(f"✗ {name} failed to start")
                if stderr:
                    print(f"  Error: {stderr.decode()[:200]}")
                return None
        except Exception as e:
            print(f"✗ Failed to start {name}: {e}")
            return None
    
    def stop_all(self):
        """Stop all running components."""
        print("\n\nStopping all V9 components...")
        
        # Stop in reverse order
        for component in reversed(COMPONENTS):
            name = component['name']
            if component['id'] in self.processes:
                process = self.processes[component['id']]
                try:
                    print(f"Stopping {name}...")
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
                    process.wait(timeout=5)
                    print(f"✓ {name} stopped")
                except subprocess.TimeoutExpired:
                    print(f"⚠ {name} did not stop gracefully, forcing...")
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except Exception as e:
                    print(f"⚠ Error stopping {name}: {e}")
        
        # Cleanup any remaining processes
        try:
            subprocess.run(['pkill', '-f', '_v9.py'], timeout=2)
        except:
            pass
        
        print("✓ All components stopped")
    
    def run(self):
        """Main execution."""
        print("=" * 60)
        print("PROJECT ASTRA NZ - ROVER MANAGER V9")
        print("=" * 60)
        
        # Setup
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
        
        print("\n" + "=" * 60)
        print("STARTING V9 COMPONENTS (in critical order)")
        print("=" * 60)
        
        # Start all components in order
        failed_critical = False
        for component in COMPONENTS:
            process = self.start_component(component)
            
            if process:
                self.processes[component['id']] = process
            elif component['critical']:
                print(f"\n✗ CRITICAL: {component['name']} failed to start")
                print("Cannot continue without critical component")
                failed_critical = True
                break
        
        if failed_critical:
            self.stop_all()
            return False
        
        # Startup complete
        print("\n" + "=" * 60)
        print("V9 STARTUP COMPLETE")
        print("=" * 60)
        print("\nActive Components:")
        for comp_id, process in self.processes.items():
            comp = next(c for c in COMPONENTS if c['id'] == comp_id)
            print(f"  • {comp['name']} (PID: {process.pid})")
        
        print("\nAccess Points:")
        print("  • Dashboard: http://10.244.77.186:8081")
        print("  • Local: http://localhost:8081")
        
        print("\nMonitoring:")
        print("  • Health Check: ./check_v9_health.sh")
        print("  • Status: cat /tmp/vision_v9/status.json")
        
        print("\nPress Ctrl+C to stop all components...")
        
        # Keep running and monitor
        try:
            while self.running:
                time.sleep(5)
                
                # Check Vision Server (critical)
                vs_process = self.processes.get(196)
                if vs_process and vs_process.poll() is not None:
                    print("\n✗ CRITICAL: Vision Server stopped unexpectedly!")
                    break
        
        except KeyboardInterrupt:
            print("\n\n⚠ Shutdown requested")
        
        finally:
            self.stop_all()
        
        return True


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

