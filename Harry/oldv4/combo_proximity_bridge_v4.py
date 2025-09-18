#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge v4
Dual sensor fusion: RPLidar S3 + Intel RealSense D435i
Ubuntu 24.04 compatible with enhanced reliability
"""

import time
import math
import threading
import numpy as np
from collections import defaultdict

# Sensor libraries
try:
    from rplidar import RPLidar
    RPLIDAR_AVAILABLE = True
except ImportError:
    print("RPLidar library not found: pip install rplidar")
    RPLIDAR_AVAILABLE = False

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    print("RealSense library not found: pip install pyrealsense2")
    REALSENSE_AVAILABLE = False

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    print("MAVLink library not found: pip install pymavlink")
    MAVLINK_AVAILABLE = False

class ComboProximityBridge:
    def __init__(self):
        # Device configurations
        self.lidar_port = '/dev/ttyUSB0'
        self.pixhawk_port = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
        self.pixhawk_baud = 57600
        
        # Fallback Pixhawk ports
        self.pixhawk_fallback_ports = [
            '/dev/ttyACM0',
            '/dev/ttyACM1', 
            '/dev/serial/by-id/usb-*Pixhawk*',
            '/dev/serial/by-id/usb-*Holybro*'
        ]
        
        # Sensor instances
        self.lidar = None
        self.realsense_pipeline = None
        self.mavlink_connection = None
        
        # Data storage
        self.proximity_data = [0] * 8  # 8 sectors, 45 degrees each
        self.data_lock = threading.Lock()
        
        # Performance tracking
        self.lidar_success_count = 0
        self.lidar_total_count = 0
        self.realsense_success_count = 0
        self.realsense_total_count = 0
        
        # System state
        self.running = True
        self.sensor_threads = []
        
        print("Project Astra NZ - Combo Proximity Bridge v4")
        print("=" * 50)

    def initialize_sensors(self):
        """Initialize all sensors with fallback options"""
        print("Initializing sensors...")
        
        # Initialize RPLidar
        if RPLIDAR_AVAILABLE:
            try:
                self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=3)
                print(f"✓ RPLidar S3 connected at {self.lidar_port}")
            except Exception as e:
                print(f"✗ RPLidar initialization failed: {e}")
                self.lidar = None
        
        # Initialize RealSense
        if REALSENSE_AVAILABLE:
            try:
                self.realsense_pipeline = rs.pipeline()
                config = rs.config()
                config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                self.realsense_pipeline.start(config)
                
                # Test frame capture
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=2000)
                if frames.get_color_frame() and frames.get_depth_frame():
                    print("✓ RealSense D435i connected and streaming")
                else:
                    raise Exception("Failed to capture test frames")
                    
            except Exception as e:
                print(f"✗ RealSense initialization failed: {e}")
                if self.realsense_pipeline:
                    try:
                        self.realsense_pipeline.stop()
                    except:
                        pass
                self.realsense_pipeline = None
        
        # Initialize MAVLink with fallback ports
        if MAVLINK_AVAILABLE:
            ports_to_try = [self.pixhawk_port] + self.pixhawk_fallback_ports
            
            for port in ports_to_try:
                try:
                    if '*' in port:  # Skip wildcard entries for now
                        continue
                        
                    self.mavlink_connection = mavutil.mavlink_connection(
                        port, baud=self.pixhawk_baud
                    )
                    self.mavlink_connection.wait_heartbeat(timeout=10)
                    print(f"✓ Pixhawk connected at {port}")
                    break
                    
                except Exception as e:
                    print(f"  Failed to connect to {port}: {e}")
                    continue
            
            if not self.mavlink_connection:
                print("✗ Could not connect to Pixhawk on any port")

    def angle_to_sector(self, angle_deg):
        """Convert angle in degrees to 8-sector index (0-7)"""
        # Normalize angle to 0-360 range
        angle_deg = angle_deg % 360
        
        # Convert to sector (0=North, 1=NE, 2=East, etc.)
        sector = int((angle_deg + 22.5) / 45) % 8
        return sector

    def collect_lidar_data(self):
        """Collect RPLidar data with enhanced error handling"""
        if not self.lidar:
            return
        
        print("Starting LiDAR data collection...")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Clear old data and restart scan
                self.lidar.stop()
                time.sleep(0.1)
                self.lidar.clear_input()
                self.lidar.start_scan()
                
                # Collect one complete scan
                sector_distances = defaultdict(list)
                scan_start_time = time.time()
                scan_timeout = 2.0  # Maximum time for one scan
                
                for measurement in self.lidar.iter_scans(scan_type='express'):
                    self.lidar_total_count += 1
                    
                    if time.time() - scan_start_time > scan_timeout:
                        break
                    
                    if not self.running:
                        break
                    
                    # Process measurements
                    for angle, distance, quality in measurement:
                        if distance > 0 and quality > 10:  # Valid measurement
                            # Convert to meters and limit range
                            distance_m = distance / 1000.0
                            if 0.2 <= distance_m <= 25.0:  # Valid range
                                sector = self.angle_to_sector(angle)
                                sector_distances[sector].append(distance_m)
                    
                    # Stop after collecting enough data
                    if len(sector_distances) >= 6:  # At least 6 sectors have data
                        break
                
                # Process sector data
                if sector_distances:
                    with self.data_lock:
                        for sector in range(8):
                            if sector in sector_distances:
                                # Use minimum distance in each sector for safety
                                self.proximity_data[sector] = min(sector_distances[sector])
                            # Keep previous value if no new data for this sector
                    
                    self.lidar_success_count += 1
                    consecutive_errors = 0
                
                time.sleep(0.05)  # Brief pause between scans
                
            except Exception as e:
                consecutive_errors += 1
                print(f"LiDAR error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print("Too many consecutive LiDAR errors, restarting connection...")
                    try:
                        self.lidar.disconnect()
                        time.sleep(2)
                        self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=3)
                        consecutive_errors = 0
                    except Exception as restart_error:
                        print(f"Failed to restart LiDAR: {restart_error}")
                        time.sleep(5)
                
                time.sleep(1)

    def collect_realsense_data(self):
        """Collect RealSense depth data for forward sector"""
        if not self.realsense_pipeline:
            return
        
        print("Starting RealSense data collection...")
        
        while self.running:
            try:
                self.realsense_total_count += 1
                
                # Get frames
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=1000)
                depth_frame = frames.get_depth_frame()
                
                if depth_frame:
                    # Convert to numpy array
                    depth_array = np.asanyarray(depth_frame.get_data())
                    height, width = depth_array.shape
                    
                    # Sample forward-facing region (center of image)
                    center_x = width // 2
                    center_y = height // 2
                    sample_size = 50  # 50x50 pixel region
                    
                    x1 = max(0, center_x - sample_size)
                    x2 = min(width, center_x + sample_size)
                    y1 = max(0, center_y - sample_size)
                    y2 = min(height, center_y + sample_size)
                    
                    # Extract center region
                    center_region = depth_array[y1:y2, x1:x2]
                    
                    # Filter valid depths (in mm)
                    valid_depths = center_region[(center_region > 200) & (center_region < 25000)]
                    
                    if len(valid_depths) > 100:  # Enough valid pixels
                        # Convert to meters and get minimum (closest obstacle)
                        min_distance = float(np.min(valid_depths)) / 1000.0
                        
                        # Update forward sector (sector 0)
                        with self.data_lock:
                            # Use RealSense data if it's closer or LiDAR has no data
                            if (self.proximity_data[0] == 0 or 
                                min_distance < self.proximity_data[0]):
                                self.proximity_data[0] = min_distance
                    
                    self.realsense_success_count += 1
                
                time.sleep(0.1)  # 10Hz update rate
                
            except Exception as e:
                print(f"RealSense error: {e}")
                time.sleep(1)

    def send_proximity_data(self):
        """Send proximity data to ArduPilot via MAVLink"""
        if not self.mavlink_connection:
            return
        
        print("Starting MAVLink proximity data transmission...")
        
        while self.running:
            try:
                with self.data_lock:
                    # Convert data to ArduPilot format
                    distances = []
                    for sector in range(8):
                        distance_cm = int(self.proximity_data[sector] * 100)  # Convert to cm
                        distance_cm = max(20, min(2500, distance_cm))  # Clamp to valid range
                        distances.append(distance_cm)
                
                # Send DISTANCE_SENSOR message for each sector
                current_time_ms = int(time.time() * 1000)
                
                for sector in range(8):
                    self.mavlink_connection.mav.distance_sensor_send(
                        current_time_ms,          # time_boot_ms
                        distances[sector],        # min_distance (cm)
                        distances[sector],        # max_distance (cm) 
                        distances[sector],        # current_distance (cm)
                        0,                        # type (0=laser)
                        sector,                   # id (sector number)
                        sector * 45,              # orientation (degrees)
                        255,                      # covariance (unknown)
                        0,                        # horizontal_fov (0=unknown)
                        0,                        # vertical_fov (0=unknown)
                        [0,0,0,0],               # quaternion (not used)
                        195                       # signal_quality (component ID)
                    )
                
                time.sleep(0.5)  # 2Hz update rate
                
            except Exception as e:
                print(f"MAVLink transmission error: {e}")
                time.sleep(1)

    def print_status(self):
        """Print system status every 10 seconds"""
        while self.running:
            try:
                # Calculate success rates
                lidar_rate = (self.lidar_success_count / max(1, self.lidar_total_count)) * 100
                realsense_rate = (self.realsense_success_count / max(1, self.realsense_total_count)) * 100
                
                # Print status
                print(f"\n{'='*60}")
                print(f"System Status - {time.strftime('%H:%M:%S')}")
                print(f"{'='*60}")
                print(f"LiDAR:    {self.lidar_success_count:4}/{self.lidar_total_count:4} ({lidar_rate:5.1f}%)")
                print(f"RealSense: {self.realsense_success_count:4}/{self.realsense_total_count:4} ({realsense_rate:5.1f}%)")
                
                # Print proximity data
                with self.data_lock:
                    print(f"\nProximity Data (meters):")
                    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                    for i, direction in enumerate(directions):
                        distance = self.proximity_data[i]
                        print(f"  {direction:2}: {distance:5.2f}m")
                
                time.sleep(10)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Status error: {e}")
                time.sleep(10)

    def run(self):
        """Main execution function"""
        try:
            # Initialize all sensors
            self.initialize_sensors()
            
            # Check if we have at least one sensor
            if not self.lidar and not self.realsense_pipeline:
                print("ERROR: No sensors available. Cannot proceed.")
                return
            
            if not self.mavlink_connection:
                print("ERROR: No MAVLink connection. Cannot send proximity data.")
                return
            
            print("\nStarting proximity sensor threads...")
            
            # Start sensor threads
            if self.lidar:
                lidar_thread = threading.Thread(target=self.collect_lidar_data, daemon=True)
                lidar_thread.start()
                self.sensor_threads.append(lidar_thread)
            
            if self.realsense_pipeline:
                realsense_thread = threading.Thread(target=self.collect_realsense_data, daemon=True)
                realsense_thread.start()
                self.sensor_threads.append(realsense_thread)
            
            # Start MAVLink transmission thread
            mavlink_thread = threading.Thread(target=self.send_proximity_data, daemon=True)
            mavlink_thread.start()
            self.sensor_threads.append(mavlink_thread)
            
            print("All threads started. Press Ctrl+C to stop.")
            print("Connect Mission Planner to UDP port 14550 for telemetry.")
            
            # Run status monitoring
            self.print_status()
            
        except KeyboardInterrupt:
            print("\n\nShutdown requested...")
            self.shutdown()
        except Exception as e:
            print(f"System error: {e}")
            self.shutdown()

    def shutdown(self):
        """Clean shutdown of all systems"""
        print("Shutting down proximity bridge...")
        self.running = False
        
        # Stop sensors
        if self.lidar:
            try:
                self.lidar.stop()
                self.lidar.disconnect()
            except:
                pass
        
        if self.realsense_pipeline:
            try:
                self.realsense_pipeline.stop()
            except:
                pass
        
        if self.mavlink_connection:
            try:
                self.mavlink_connection.close()
            except:
                pass
        
        print("Shutdown complete")

if __name__ == "__main__":
    # Check dependencies
    if not RPLIDAR_AVAILABLE and not REALSENSE_AVAILABLE:
        print("ERROR: No sensor libraries available")
        print("Install with: pip install rplidar pyrealsense2")
        exit(1)
    
    if not MAVLINK_AVAILABLE:
        print("ERROR: MAVLink library not available")
        print("Install with: pip install pymavlink")
        exit(1)
    
    # Run proximity bridge
    bridge = ComboProximityBridge()
    bridge.run()
