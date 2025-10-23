#!/usr/bin/env python3
"""
Rover-Vision Port Detector
Automatically detects and maps hardware ports for LiDAR, Pixhawk, and RealSense
Handles port changes and provides fallback detection methods
"""

import os
import re
import subprocess
import json
import time
from typing import Dict, List, Optional, Tuple

class PortDetector:
    """Robust port detection system for rover hardware"""
    
    def __init__(self):
        """Initialize port detector with multiple detection methods"""
        self.detected_ports = {
            'lidar': None,
            'pixhawk': None,
            'realsense': None
        }
        
        # Port patterns for different hardware
        self.port_patterns = {
            'lidar': {
                'usb_vendor': '10c4',  # Silicon Labs
                'usb_product': 'ea60',  # CP210x UART Bridge
                'device_name': 'rplidar',
                'port_patterns': ['/dev/ttyUSB*', '/dev/ttyACM*']
            },
            'pixhawk': {
                'usb_vendor': '2dae',  # Holybro
                'usb_product': '0010',  # Pixhawk
                'device_name': 'pixhawk',
                'port_patterns': ['/dev/ttyACM*']
            },
            'realsense': {
                'usb_vendor': '8086',  # Intel
                'usb_product': '0b3a',  # RealSense
                'device_name': 'realsense',
                'port_patterns': ['/dev/video*']
            }
        }
        
        print("[PORT_DETECTOR] Initialized with robust detection methods")
    
    def run_command(self, command: str) -> Tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timeout"
        except Exception as e:
            return -1, "", str(e)
    
    def detect_usb_devices(self) -> List[Dict]:
        """Detect USB devices using lsusb"""
        devices = []
        
        try:
            exit_code, stdout, stderr = self.run_command("lsusb")
            if exit_code != 0:
                print(f"[WARNING] lsusb failed: {stderr}")
                return devices
            
            for line in stdout.split('\n'):
                if 'ID' in line:
                    # Parse USB device info
                    match = re.search(r'ID (\w+):(\w+)', line)
                    if match:
                        vendor_id, product_id = match.groups()
                        devices.append({
                            'vendor_id': vendor_id,
                            'product_id': product_id,
                            'description': line.strip()
                        })
            
        except Exception as e:
            print(f"[ERROR] USB detection failed: {e}")
        
        return devices
    
    def detect_serial_ports(self) -> List[str]:
        """Detect available serial ports"""
        ports = []
        
        # Check common serial port locations
        port_locations = [
            '/dev/ttyUSB*',
            '/dev/ttyACM*',
            '/dev/ttyS*'
        ]
        
        for pattern in port_locations:
            try:
                exit_code, stdout, stderr = self.run_command(f"ls {pattern} 2>/dev/null")
                if exit_code == 0:
                    for port in stdout.strip().split('\n'):
                        if port and os.path.exists(port):
                            ports.append(port)
            except Exception as e:
                print(f"[WARNING] Failed to check {pattern}: {e}")
        
        return sorted(ports)
    
    def detect_video_devices(self) -> List[str]:
        """Detect video devices (for RealSense)"""
        devices = []
        
        try:
            exit_code, stdout, stderr = self.run_command("ls /dev/video* 2>/dev/null")
            if exit_code == 0:
                for device in stdout.strip().split('\n'):
                    if device and os.path.exists(device):
                        devices.append(device)
        except Exception as e:
            print(f"[WARNING] Video device detection failed: {e}")
        
        return sorted(devices)
    
    def test_port_communication(self, port: str, device_type: str) -> bool:
        """Test if a port can communicate with the expected device"""
        try:
            if device_type == 'lidar':
                # Test LiDAR communication
                from rplidar import RPLidar
                lidar = RPLidar(port)
                info = lidar.get_info()
                lidar.disconnect()
                return True
                
            elif device_type == 'pixhawk':
                # Test Pixhawk communication
                from pymavlink import mavutil
                connection = mavutil.mavlink_connection(port, baud=57600)
                # Try to get heartbeat with timeout
                connection.wait_heartbeat(timeout=5)
                connection.close()
                return True
                
            elif device_type == 'realsense':
                # Test RealSense communication
                import pyrealsense2 as rs
                pipeline = rs.pipeline()
                config = rs.config()
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                pipeline.start(config)
                frames = pipeline.wait_for_frames(timeout_ms=1000)
                pipeline.stop()
                return True
                
        except Exception as e:
            print(f"[DEBUG] Port {port} test failed for {device_type}: {e}")
            return False
        
        return False
    
    def detect_lidar_port(self) -> Optional[str]:
        """Detect LiDAR port using multiple methods"""
        print("[DETECT] Searching for LiDAR port...")
        
        # Method 1: Check USB devices
        usb_devices = self.detect_usb_devices()
        for device in usb_devices:
            if (device['vendor_id'] == self.port_patterns['lidar']['usb_vendor'] and
                device['product_id'] == self.port_patterns['lidar']['usb_product']):
                print(f"[DETECT] Found LiDAR USB device: {device['description']}")
                break
        
        # Method 2: Check serial ports
        serial_ports = self.detect_serial_ports()
        for port in serial_ports:
            print(f"[DETECT] Testing port {port} for LiDAR...")
            if self.test_port_communication(port, 'lidar'):
                print(f"[SUCCESS] LiDAR found at {port}")
                return port
        
        # Method 3: Check for symlinks
        symlink_paths = ['/dev/rplidar', '/dev/lidar']
        for symlink in symlink_paths:
            if os.path.exists(symlink):
                print(f"[SUCCESS] LiDAR found at symlink {symlink}")
                return symlink
        
        print("[WARNING] LiDAR port not detected")
        return None
    
    def detect_pixhawk_port(self) -> Optional[str]:
        """Detect Pixhawk port using multiple methods"""
        print("[DETECT] Searching for Pixhawk port...")
        
        # Method 1: Check USB devices
        usb_devices = self.detect_usb_devices()
        for device in usb_devices:
            if (device['vendor_id'] == self.port_patterns['pixhawk']['usb_vendor'] and
                device['product_id'] == self.port_patterns['pixhawk']['usb_product']):
                print(f"[DETECT] Found Pixhawk USB device: {device['description']}")
                break
        
        # Method 2: Check ACM ports (common for Pixhawk)
        acm_ports = [port for port in self.detect_serial_ports() if 'ttyACM' in port]
        for port in acm_ports:
            print(f"[DETECT] Testing port {port} for Pixhawk...")
            if self.test_port_communication(port, 'pixhawk'):
                print(f"[SUCCESS] Pixhawk found at {port}")
                return port
        
        # Method 3: Check for symlinks
        symlink_paths = ['/dev/pixhawk', '/dev/autopilot']
        for symlink in symlink_paths:
            if os.path.exists(symlink):
                print(f"[SUCCESS] Pixhawk found at symlink {symlink}")
                return symlink
        
        print("[WARNING] Pixhawk port not detected")
        return None
    
    def detect_realsense_port(self) -> Optional[str]:
        """Detect RealSense port using multiple methods"""
        print("[DETECT] Searching for RealSense port...")
        
        # Method 1: Check USB devices
        usb_devices = self.detect_usb_devices()
        for device in usb_devices:
            if (device['vendor_id'] == self.port_patterns['realsense']['usb_vendor'] and
                device['product_id'] == self.port_patterns['realsense']['usb_product']):
                print(f"[DETECT] Found RealSense USB device: {device['description']}")
                break
        
        # Method 2: Check video devices
        video_devices = self.detect_video_devices()
        for device in video_devices:
            print(f"[DETECT] Testing video device {device} for RealSense...")
            if self.test_port_communication(device, 'realsense'):
                print(f"[SUCCESS] RealSense found at {device}")
                return device
        
        # Method 3: Check for symlinks
        symlink_paths = ['/dev/realsense', '/dev/camera']
        for symlink in symlink_paths:
            if os.path.exists(symlink):
                print(f"[SUCCESS] RealSense found at symlink {symlink}")
                return symlink
        
        print("[WARNING] RealSense port not detected")
        return None
    
    def detect_all_ports(self) -> Dict[str, Optional[str]]:
        """Detect all hardware ports"""
        print("[DETECT] Starting comprehensive port detection...")
        
        # Detect each device type
        self.detected_ports['lidar'] = self.detect_lidar_port()
        self.detected_ports['pixhawk'] = self.detect_pixhawk_port()
        self.detected_ports['realsense'] = self.detect_realsense_port()
        
        # Print results
        print("\n" + "="*50)
        print("PORT DETECTION RESULTS")
        print("="*50)
        for device_type, port in self.detected_ports.items():
            status = "✓ FOUND" if port else "✗ NOT FOUND"
            print(f"{device_type.upper():12} {status:12} {port or 'N/A'}")
        print("="*50)
        
        return self.detected_ports
    
    def save_port_config(self, config_file: str = "detected_ports.json"):
        """Save detected ports to configuration file"""
        try:
            with open(config_file, 'w') as f:
                json.dump(self.detected_ports, f, indent=2)
            print(f"[SAVE] Port configuration saved to {config_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save port configuration: {e}")
    
    def load_port_config(self, config_file: str = "detected_ports.json") -> Dict[str, Optional[str]]:
        """Load port configuration from file"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    print(f"[LOAD] Port configuration loaded from {config_file}")
                    return config
        except Exception as e:
            print(f"[ERROR] Failed to load port configuration: {e}")
        
        return {}
    
    def verify_ports(self) -> bool:
        """Verify that all detected ports are still accessible"""
        print("[VERIFY] Verifying port accessibility...")
        
        all_accessible = True
        
        for device_type, port in self.detected_ports.items():
            if port:
                if os.path.exists(port):
                    print(f"[VERIFY] ✓ {device_type} port {port} is accessible")
                else:
                    print(f"[VERIFY] ✗ {device_type} port {port} is not accessible")
                    all_accessible = False
            else:
                print(f"[VERIFY] ⚠ {device_type} port not detected")
        
        return all_accessible
    
    def auto_detect_and_update_config(self, config_file: str = "rover_config_v9.json"):
        """Automatically detect ports and update main configuration"""
        print("[AUTO] Starting automatic port detection and config update...")
        
        # Detect all ports
        detected_ports = self.detect_all_ports()
        
        # Load existing configuration
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"[WARNING] Configuration file {config_file} not found, creating new one")
            config = {}
        except Exception as e:
            print(f"[ERROR] Failed to load configuration: {e}")
            config = {}
        
        # Update configuration with detected ports
        if 'hardware' not in config:
            config['hardware'] = {}
        
        if detected_ports['lidar']:
            config['hardware']['lidar_port'] = detected_ports['lidar']
            print(f"[UPDATE] Updated LiDAR port to {detected_ports['lidar']}")
        
        if detected_ports['pixhawk']:
            config['hardware']['pixhawk_port'] = detected_ports['pixhawk']
            print(f"[UPDATE] Updated Pixhawk port to {detected_ports['pixhawk']}")
        
        if detected_ports['realsense']:
            config['hardware']['realsense_port'] = detected_ports['realsense']
            print(f"[UPDATE] Updated RealSense port to {detected_ports['realsense']}")
        
        # Save updated configuration
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"[SAVE] Configuration updated in {config_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save configuration: {e}")
        
        return detected_ports

def main():
    """Main function for port detection"""
    print("="*60)
    print("Rover-Vision Port Detector")
    print("="*60)
    
    detector = PortDetector()
    
    # Auto-detect and update configuration
    detected_ports = detector.auto_detect_and_update_config()
    
    # Verify ports
    if detector.verify_ports():
        print("\n[SUCCESS] All detected ports are accessible")
    else:
        print("\n[WARNING] Some ports are not accessible")
    
    # Save port configuration
    detector.save_port_config()
    
    print("\n[COMPLETE] Port detection completed")

if __name__ == "__main__":
    main()
