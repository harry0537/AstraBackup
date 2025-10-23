#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V9
Enhanced proximity bridge with GPS integration and improved reliability
Component 195 - Production Ready - V9 with GPS data capture
"""

import time
import threading
import numpy as np
import json
import os
import sys
from rplidar import RPLidar
from pymavlink import mavutil

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

# Import port detector
try:
    from port_detector import PortDetector
    PORT_DETECTOR_AVAILABLE = True
except ImportError:
    PORT_DETECTOR_AVAILABLE = False
    print("[WARNING] Port detector not available, using static configuration")

# Hardware configuration - Load from config file with auto-detection
def load_hardware_config():
    """Load hardware configuration from rover_config_v9.json with auto-detection"""
    config_file = "rover_config_v9.json"
    default_config = {
        'lidar_port': '/dev/ttyUSB0',
        'pixhawk_port': '/dev/ttyACM0',
        'realsense_config': {'width': 424, 'height': 240, 'fps': 15}
    }

    # Try to load from config file first
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                print(f"[CONFIG] Loaded hardware config from {config_file}")
                
                # Check if ports are still accessible
                lidar_port = config.get('lidar_port', default_config['lidar_port'])
                pixhawk_port = config.get('pixhawk_port', default_config['pixhawk_port'])
                
                # Verify ports are accessible
                if os.path.exists(lidar_port) and os.path.exists(pixhawk_port):
                return {
                        'lidar_port': lidar_port,
                        'pixhawk_port': pixhawk_port,
                    'realsense_config': config.get('realsense_config', default_config['realsense_config'])
                }
                else:
                    print("[WARNING] Configured ports are not accessible, attempting auto-detection")
                    
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}, attempting auto-detection")
    
    # Auto-detect ports if available
    if PORT_DETECTOR_AVAILABLE:
        print("[AUTO] Attempting automatic port detection...")
        try:
            detector = PortDetector()
            detected_ports = detector.detect_all_ports()
            
            # Use detected ports or fall back to defaults
            lidar_port = detected_ports.get('lidar') or default_config['lidar_port']
            pixhawk_port = detected_ports.get('pixhawk') or default_config['pixhawk_port']
            
            print(f"[AUTO] Detected ports - LiDAR: {lidar_port}, Pixhawk: {pixhawk_port}")
            
            return {
                'lidar_port': lidar_port,
                'pixhawk_port': pixhawk_port,
                'realsense_config': default_config['realsense_config']
            }
            
        except Exception as e:
            print(f"[ERROR] Auto-detection failed: {e}, using defaults")

    print("[WARNING] Using default hardware configuration")
    return default_config

# Load hardware configuration
HARDWARE_CONFIG = load_hardware_config()

# Configuration constants
LIDAR_PORT = HARDWARE_CONFIG['lidar_port']
PIXHAWK_PORT = HARDWARE_CONFIG['pixhawk_port']
REALSENSE_CONFIG = HARDWARE_CONFIG['realsense_config']

# Proximity detection parameters
SECTOR_COUNT = 8  # Number of sectors for proximity detection
MAX_DISTANCE_CM = 300  # Maximum distance to consider for proximity
PROXIMITY_THRESHOLD_CM = 100  # Distance threshold for proximity warning

# MAVLink configuration
MAVLINK_ENABLED = True
MAVLINK_PORT = 14550  # Standard MAVLink port

# Data storage
TELEMETRY_FILE = "/tmp/proximity_v9.json"
GPS_DATA_FILE = "/tmp/gps_v9.json"

class ProximityBridge:
    """Enhanced proximity bridge with GPS integration and improved reliability"""
    
    def __init__(self):
        """Initialize the proximity bridge with all sensors and communication"""
        self.running = False
        self.lidar = None
        self.pixhawk = None
        self.realsense_pipeline = None
        self.realsense_config = None
        
        # Port monitoring
        self.port_check_interval = 30  # Check ports every 30 seconds
        self.last_port_check = 0
        self.port_detector = None
        
        # Data storage
        self.proximity_data = {
            'timestamp': time.time(),
            'sectors': [0] * SECTOR_COUNT,
            'obstacles': [],
            'closest_obstacle': None,
            'proximity_warning': False
        }
        
        self.gps_data = {
            'timestamp': time.time(),
            'latitude': 0.0,
            'longitude': 0.0,
            'altitude': 0.0,
            'heading': 0.0,
            'speed': 0.0,
            'satellites': 0,
            'fix_quality': 0
        }
        
        # Threading
        self.lidar_thread = None
        self.realsense_thread = None
        self.mavlink_thread = None
        self.data_thread = None
        
        # Initialize port detector if available
        if PORT_DETECTOR_AVAILABLE:
            try:
                self.port_detector = PortDetector()
                print("[INIT] Port detector initialized")
            except Exception as e:
                print(f"[WARNING] Failed to initialize port detector: {e}")
                self.port_detector = None
        
        print("[INIT] Proximity Bridge V9 initialized")
    
    def check_port_changes(self):
        """Check for port changes and reconnect if necessary"""
        current_time = time.time()
        
        # Only check ports periodically
        if current_time - self.last_port_check < self.port_check_interval:
            return
        
        self.last_port_check = current_time
        
        if not self.port_detector:
            return
        
        print("[PORT_CHECK] Checking for port changes...")
        
        try:
            # Detect current ports
            detected_ports = self.port_detector.detect_all_ports()
            
            # Check if LiDAR port changed
            if detected_ports.get('lidar') and detected_ports['lidar'] != LIDAR_PORT:
                print(f"[PORT_CHECK] LiDAR port changed from {LIDAR_PORT} to {detected_ports['lidar']}")
                # Reconnect LiDAR
                if self.lidar:
                    self.lidar.disconnect()
                self.lidar = None
                # Update global port
                global LIDAR_PORT
                LIDAR_PORT = detected_ports['lidar']
                # Reconnect
                self.connect_lidar()
            
            # Check if Pixhawk port changed
            if detected_ports.get('pixhawk') and detected_ports['pixhawk'] != PIXHAWK_PORT:
                print(f"[PORT_CHECK] Pixhawk port changed from {PIXHAWK_PORT} to {detected_ports['pixhawk']}")
                # Reconnect Pixhawk
                if self.pixhawk:
                    self.pixhawk.close()
                self.pixhawk = None
                # Update global port
                global PIXHAWK_PORT
                PIXHAWK_PORT = detected_ports['pixhawk']
                # Reconnect
                self.connect_pixhawk()
                
        except Exception as e:
            print(f"[ERROR] Port check failed: {e}")
    
    def connect_lidar(self):
        """Connect to RPLidar with enhanced error handling"""
            try:
            print(f"[LIDAR] Connecting to {LIDAR_PORT}...")
            self.lidar = RPLidar(LIDAR_PORT)

            # Get device info
                info = self.lidar.get_info()
            print(f"[LIDAR] Connected: {info}")
            
            # Start scanning
            self.lidar.start_motor()
            print("[LIDAR] Motor started successfully")
                return True

            except Exception as e:
            print(f"[ERROR] Failed to connect to LiDAR: {e}")
                    return False

    def connect_pixhawk(self):
        """Connect to Pixhawk with enhanced error handling"""
        try:
            print(f"[PIXHAWK] Connecting to {PIXHAWK_PORT}...")
            self.pixhawk = mavutil.mavlink_connection(PIXHAWK_PORT, baud=57600)
            
            # Wait for heartbeat
            print("[PIXHAWK] Waiting for heartbeat...")
            self.pixhawk.wait_heartbeat()
            print(f"[PIXHAWK] Heartbeat from system {self.pixhawk.target_system}")
            
                                return True

                except Exception as e:
            print(f"[ERROR] Failed to connect to Pixhawk: {e}")
            return False

    def connect_realsense(self):
        """Connect to RealSense camera with enhanced error handling"""
        if not REALSENSE_AVAILABLE:
            print("[WARNING] RealSense not available, skipping camera")
            return False

        try:
            print("[REALSENSE] Connecting to RealSense camera...")
            self.realsense_pipeline = rs.pipeline()
            self.realsense_config = rs.config()
            
            # Configure streams
            self.realsense_config.enable_stream(rs.stream.depth, 
                                              REALSENSE_CONFIG['width'], 
                                              REALSENSE_CONFIG['height'], 
                                              rs.format.z16, 
                                              REALSENSE_CONFIG['fps'])
            
            self.realsense_config.enable_stream(rs.stream.color, 
                                              REALSENSE_CONFIG['width'], 
                                              REALSENSE_CONFIG['height'], 
                                              rs.format.bgr8, 
                                              REALSENSE_CONFIG['fps'])
            
            # Start pipeline
            self.realsense_pipeline.start(self.realsense_config)
            print("[REALSENSE] Pipeline started successfully")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to RealSense: {e}")
            return False

    def process_lidar_data(self, scan_data):
        """Process LiDAR data and update proximity information"""
        try:
            # Convert scan data to numpy array for processing
            points = np.array([[point[0], point[1]] for point in scan_data])
            
            if len(points) == 0:
                return
            
            # Calculate distances and angles
            distances = np.sqrt(points[:, 0]**2 + points[:, 1]**2)
            angles = np.arctan2(points[:, 1], points[:, 0])
            
            # Convert to degrees and normalize
            angles_deg = np.degrees(angles)
            angles_deg = (angles_deg + 360) % 360
            
            # Initialize sector data
            sectors = [0] * SECTOR_COUNT
            obstacles = []
            
            # Process each point
            for i, (distance, angle) in enumerate(zip(distances, angles_deg)):
                if distance > 0 and distance < MAX_DISTANCE_CM:
                    # Determine sector
                    sector = int(angle / (360 / SECTOR_COUNT)) % SECTOR_COUNT
                    sectors[sector] = max(sectors[sector], distance)
                    
                    # Add to obstacles if close
                    if distance < PROXIMITY_THRESHOLD_CM:
                        obstacles.append({
                            'distance': distance,
                            'angle': angle,
                            'sector': sector
                        })
            
            # Update proximity data
            self.proximity_data.update({
                'timestamp': time.time(),
                'sectors': sectors,
                'obstacles': obstacles,
                'closest_obstacle': min(obstacles, key=lambda x: x['distance']) if obstacles else None,
                'proximity_warning': len(obstacles) > 0
            })
            
        except Exception as e:
            print(f"[ERROR] Failed to process LiDAR data: {e}")
    
    def process_gps_data(self):
        """Process GPS data from Pixhawk"""
        try:
            if not self.pixhawk:
                return
            
            # Request GPS status
            self.pixhawk.mav.request_data_stream_send(
                self.pixhawk.target_system,
                self.pixhawk.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                1,  # 1 Hz
                1   # Enable
            )
            
            # Get GPS data
            msg = self.pixhawk.recv_match(type='GPS_RAW_INT', blocking=False)
            if msg:
                self.gps_data.update({
                    'timestamp': time.time(),
                    'latitude': msg.lat / 1e7,
                    'longitude': msg.lon / 1e7,
                    'altitude': msg.alt / 1000.0,
                    'heading': msg.cog / 100.0,
                    'speed': msg.vel / 100.0,
                    'satellites': msg.satellites_visible,
                    'fix_quality': msg.fix_type
                })

        except Exception as e:
            print(f"[ERROR] Failed to process GPS data: {e}")
    
    def send_mavlink_data(self):
        """Send proximity data to Pixhawk via MAVLink"""
        try:
            if not self.pixhawk or not MAVLINK_ENABLED:
                return
            
            # Send proximity data as custom message
            # This is a simplified example - you'd need to implement proper MAVLink messages
            for i, distance in enumerate(self.proximity_data['sectors']):
                if distance > 0:
                    # Send obstacle distance for each sector
                    # This would need proper MAVLink message implementation
                    pass
                    
        except Exception as e:
            print(f"[ERROR] Failed to send MAVLink data: {e}")
    
    def save_telemetry_data(self):
        """Save telemetry data to files"""
        try:
            # Save proximity data
            with open(TELEMETRY_FILE, 'w') as f:
                json.dump(self.proximity_data, f, indent=2)
            
            # Save GPS data
            with open(GPS_DATA_FILE, 'w') as f:
                json.dump(self.gps_data, f, indent=2)
                
        except Exception as e:
            print(f"[ERROR] Failed to save telemetry data: {e}")
    
    def lidar_worker(self):
        """LiDAR data processing worker thread"""
        print("[LIDAR] Starting LiDAR worker thread")
        
        while self.running:
            try:
                if self.lidar:
                    # Get scan data
                    scan_data = list(self.lidar.iter_scans(max_buf_meas=1000))
                    if scan_data:
                        self.process_lidar_data(scan_data[0])
                        
            except Exception as e:
                print(f"[ERROR] LiDAR worker error: {e}")
                time.sleep(1)
            
            time.sleep(0.1)  # 10 Hz update rate
    
    def realsense_worker(self):
        """RealSense data processing worker thread"""
        print("[REALSENSE] Starting RealSense worker thread")
        
        while self.running:
            try:
                if self.realsense_pipeline:
                    # Get frames
                    frames = self.realsense_pipeline.wait_for_frames()
                    # Process depth data for obstacle detection
                    # This is a simplified example

                except Exception as e:
                print(f"[ERROR] RealSense worker error: {e}")
                time.sleep(1)
            
            time.sleep(0.1)  # 10 Hz update rate
    
    def mavlink_worker(self):
        """MAVLink communication worker thread"""
        print("[MAVLINK] Starting MAVLink worker thread")
        
        while self.running:
            try:
                if self.pixhawk:
                    # Process GPS data
                    self.process_gps_data()
                    
                    # Send proximity data
                    self.send_mavlink_data()
                    
            except Exception as e:
                print(f"[ERROR] MAVLink worker error: {e}")
                        time.sleep(1)

            time.sleep(0.1)  # 10 Hz update rate
    
    def data_worker(self):
        """Data saving worker thread"""
        print("[DATA] Starting data worker thread")
        
        while self.running:
            try:
                # Save telemetry data
                self.save_telemetry_data()
                
            except Exception as e:
                print(f"[ERROR] Data worker error: {e}")
                time.sleep(1)
            
            time.sleep(1)  # 1 Hz update rate
    
    def start(self):
        """Start the proximity bridge"""
        print("[START] Starting Proximity Bridge V9...")
        
        # Connect to hardware
        lidar_connected = self.connect_lidar()
        pixhawk_connected = self.connect_pixhawk()
        realsense_connected = self.connect_realsense()
        
        if not lidar_connected:
            print("[ERROR] Failed to connect to LiDAR - cannot start")
            return False
        
        print(f"[START] Hardware status - LiDAR: {lidar_connected}, Pixhawk: {pixhawk_connected}, RealSense: {realsense_connected}")
        
        # Start worker threads
        self.running = True
        
        if lidar_connected:
            self.lidar_thread = threading.Thread(target=self.lidar_worker, daemon=True)
            self.lidar_thread.start()
        
        if realsense_connected:
            self.realsense_thread = threading.Thread(target=self.realsense_worker, daemon=True)
            self.realsense_thread.start()
        
        if pixhawk_connected:
            self.mavlink_thread = threading.Thread(target=self.mavlink_worker, daemon=True)
            self.mavlink_thread.start()
        
        # Always start data worker
        self.data_thread = threading.Thread(target=self.data_worker, daemon=True)
        self.data_thread.start()
        
        print("[START] Proximity Bridge V9 started successfully")
        return True
    
    def stop(self):
        """Stop the proximity bridge"""
        print("[STOP] Stopping Proximity Bridge V9...")
        
        self.running = False
        
        # Stop LiDAR
        if self.lidar:
            try:
                self.lidar.stop_motor()
                self.lidar.disconnect()
            except:
                pass
        
        # Stop RealSense
        if self.realsense_pipeline:
            try:
                self.realsense_pipeline.stop()
            except:
                pass

        # Close Pixhawk connection
        if self.pixhawk:
            try:
                self.pixhawk.close()
        except:
            pass

        print("[STOP] Proximity Bridge V9 stopped")

    def run(self):
        """Main run loop"""
        try:
            if self.start():
                print("[RUN] Proximity Bridge V9 running...")
                
                # Main loop
                while self.running:
                    try:
                        # Check for port changes
                        self.check_port_changes()
                        
                        # Print status every 10 seconds
                        if int(time.time()) % 10 == 0:
                            print(f"[STATUS] Sectors: {self.proximity_data['sectors']}")
                            print(f"[STATUS] GPS: Lat={self.gps_data['latitude']:.6f}, Lon={self.gps_data['longitude']:.6f}")
                            print(f"[STATUS] Ports - LiDAR: {LIDAR_PORT}, Pixhawk: {PIXHAWK_PORT}")
                        
                        time.sleep(1)

        except KeyboardInterrupt:
                        print("[INTERRUPT] Received interrupt signal")
                        break
                        
            else:
                print("[ERROR] Failed to start Proximity Bridge V9")
                
        except Exception as e:
            print(f"[ERROR] Proximity Bridge V9 error: {e}")

        finally:
            self.stop()

def main():
    """Main function"""
    print("=" * 50)
    print("Project Astra NZ - Proximity Bridge V9")
    print("=" * 50)
    
    # Create and run proximity bridge
    bridge = ProximityBridge()
    bridge.run()

if __name__ == "__main__":
    main()