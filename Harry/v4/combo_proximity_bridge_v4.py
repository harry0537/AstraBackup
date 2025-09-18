#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V4 (Component 195)
Dual sensor fusion: RPLidar S3 + Intel RealSense D435i
"""

import time
import threading
import numpy as np
from rplidar import RPLidar
from pymavlink import mavutil
import pyrealsense2 as rs

# CRITICAL: Never modify these values
LIDAR_PORT = '/dev/ttyUSB0'
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600
COMPONENT_ID = 195

class ComboProximityBridge:
    def __init__(self):
        self.lidar = None
        self.mavlink = None
        self.pipeline = None
        self.running = True
        
        # Sensor data storage
        self.lidar_distances = [25.0] * 8  # 8 sectors, 45° each
        self.realsense_distance = 25.0
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'lidar_success': 0,
            'lidar_errors': 0,
            'realsense_success': 0,
            'messages_sent': 0,
            'start_time': time.time()
        }
        
    def connect_lidar(self):
        """Connect to RPLidar S3"""
        try:
            print(f"Connecting to RPLidar at {LIDAR_PORT}")
            self.lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=2)
            
            # Reset and check health
            self.lidar.clean_input()
            info = self.lidar.get_info()
            print(f"✓ RPLidar connected: {info}")
            
            health = self.lidar.get_health()
            if health[0] != 'Good':
                print(f"⚠ LiDAR health: {health[0]}")
                
            # Start motor
            self.lidar.start_motor()
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"✗ RPLidar connection failed: {e}")
            return False
            
    def connect_realsense(self):
        """Connect to Intel RealSense D435i"""
        try:
            print("Connecting to RealSense D435i")
            self.pipeline = rs.pipeline()
            config = rs.config()
            
            # Configure depth stream
            config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
            
            # Start pipeline
            self.pipeline.start(config)
            
            # Test frames
            for _ in range(5):
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                if frames.get_depth_frame():
                    print("✓ RealSense connected and streaming")
                    return True
                    
            print("✗ RealSense not receiving frames")
            return False
            
        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            return False
            
    def connect_pixhawk(self):
        """Connect to Pixhawk via MAVLink"""
        try:
            print(f"Connecting to Pixhawk at {PIXHAWK_PORT}")
            self.mavlink = mavutil.mavlink_connection(
                PIXHAWK_PORT,
                baud=PIXHAWK_BAUD,
                source_system=255,
                source_component=COMPONENT_ID
            )
            
            # Wait for heartbeat
            self.mavlink.wait_heartbeat(timeout=10)
            print("✓ Connected to Pixhawk")
            
            # Request distance sensor stream
            self.mavlink.mav.request_data_stream_send(
                self.mavlink.target_system,
                self.mavlink.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA3,
                10,
                1
            )
            
            return True
            
        except Exception as e:
            print(f"✗ Pixhawk connection failed: {e}")
            return False
            
    def lidar_thread(self):
        """Thread for RPLidar data processing"""
        error_count = 0
        
        while self.running:
            if not self.lidar:
                time.sleep(1)
                continue
                
            try:
                # Clear buffer to prevent overflow
                self.lidar.clean_input()
                
                # Get scan data with timeout
                scan = list(self.lidar.iter_scan(max_buf_meas=0, min_len=200))
                
                if scan:
                    # Process scan into 8 sectors
                    sector_data = [[] for _ in range(8)]
                    
                    for quality, angle, distance in scan:
                        if quality > 0 and 200 < distance < 25000:
                            # Direct angle mapping (0° = front)
                            sector = int((angle % 360) / 45)
                            sector_data[sector].append(distance / 1000.0)
                            
                    # Update distances with minimum per sector
                    with self.lock:
                        for i, data in enumerate(sector_data):
                            if data:
                                self.lidar_distances[i] = min(data)
                            else:
                                self.lidar_distances[i] = 25.0
                                
                    self.stats['lidar_success'] += 1
                    error_count = 0
                    
            except Exception as e:
                error_count += 1
                self.stats['lidar_errors'] += 1
                
                if error_count > 5:
                    print(f"RPLidar errors: {error_count}, attempting recovery")
                    try:
                        self.lidar.stop()
                        self.lidar.stop_motor()
                        self.lidar.disconnect()
                    except:
                        pass
                    
                    time.sleep(2)
                    self.connect_lidar()
                    error_count = 0
                    
    def realsense_thread(self):
        """Thread for RealSense depth processing"""
        while self.running:
            if not self.pipeline:
                time.sleep(1)
                continue
                
            try:
                # Get frames
                frames = self.pipeline.wait_for_frames(timeout_ms=100)
                depth_frame = frames.get_depth_frame()
                
                if depth_frame:
                    # Get center region depth (more stable than single point)
                    width = depth_frame.get_width()
                    height = depth_frame.get_height()
                    
                    # Sample center 10x10 pixel area
                    center_x = width // 2
                    center_y = height // 2
                    
                    distances = []
                    for x in range(center_x - 5, center_x + 5):
                        for y in range(center_y - 5, center_y + 5):
                            dist = depth_frame.get_distance(x, y)
                            if 0.2 < dist < 25.0:  # Valid range
                                distances.append(dist)
                                
                    if distances:
                        with self.lock:
                            self.realsense_distance = min(distances)
                    else:
                        with self.lock:
                            self.realsense_distance = 25.0
                            
                    self.stats['realsense_success'] += 1
                    
            except Exception as e:
                # Silent fail for RealSense
                pass
                
    def send_proximity_data(self):
        """Send combined sensor data to ArduPilot"""
        if not self.mavlink:
            return
            
        timestamp = int(time.time() * 1000)
        
        with self.lock:
            # Sectors 0-2: Use RealSense (forward facing)
            # Sectors 3-7: Use RPLidar (sides and rear)
            combined_distances = self.lidar_distances.copy()
            
            # Override forward sectors with RealSense if closer
            for i in range(3):  # Sectors 0, 1, 2 (front)
                if self.realsense_distance < combined_distances[i]:
                    combined_distances[i] = self.realsense_distance
                    
        # Send DISTANCE_SENSOR messages for each sector
        for sector in range(8):
            distance_cm = int(combined_distances[sector] * 100)
            orientation = sector * 45
            
            # MAV_DISTANCE_SENSOR_LASER type = 0
            self.mavlink.mav.distance_sensor_send(
                timestamp,           # time_boot_ms
                200,                # min_distance (cm)
                2500,               # max_distance (cm)
                distance_cm,        # current_distance
                0,                  # type: MAV_DISTANCE_SENSOR_LASER
                0,                  # id
                orientation,        # orientation (MAV_SENSOR_ROTATION)
                255,                # covariance
                0.0,                # horizontal_fov
                0.0,                # vertical_fov
                [0.0] * 4,          # quaternion
                255                 # signal_quality
            )
            
        self.stats['messages_sent'] += 8
        
    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        
        with self.lock:
            lidar_min = min(self.lidar_distances)
            realsense = self.realsense_distance
            
        print(f"\r[{uptime:4d}s] LiDAR: {self.stats['lidar_success']:4d} OK, "
              f"{self.stats['lidar_errors']:3d} ERR | "
              f"RealSense: {self.stats['realsense_success']:4d} OK | "
              f"Sent: {self.stats['messages_sent']:5d} | "
              f"Min: L={lidar_min:.1f}m R={realsense:.1f}m", end='')
              
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V4 - Component 195")
        print("=" * 60)
        
        # Connect all systems
        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense()
        
        if not pixhawk_ok:
            print("❌ Cannot continue without Pixhawk connection")
            return
            
        if not lidar_ok and not realsense_ok:
            print("❌ No sensors available")
            return
            
        # Start sensor threads
        if lidar_ok:
            lidar_thread = threading.Thread(target=self.lidar_thread)
            lidar_thread.daemon = True
            lidar_thread.start()
            
        if realsense_ok:
            rs_thread = threading.Thread(target=self.realsense_thread)
            rs_thread.daemon = True
            rs_thread.start()
            
        print("\n✓ Proximity bridge operational")
        print("  • Sending 8-sector data to Mission Planner")
        print("  • Forward sectors: RealSense priority")
        print("  • Side/rear sectors: RPLidar data\n")
        
        # Main loop
        try:
            last_send = time.time()
            last_status = time.time()
            
            while self.running:
                # Send data at 10Hz
                if time.time() - last_send > 0.1:
                    self.send_proximity_data()
                    last_send = time.time()
                    
                # Print status at 1Hz
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()
                    
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\nShutting down proximity bridge...")
            
        finally:
            self.running = False
            
            if self.lidar:
                try:
                    self.lidar.stop()
                    self.lidar.stop_motor()
                    self.lidar.disconnect()
                except:
                    pass
                    
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
                    
            print("✓ Proximity bridge stopped")

if __name__ == "__main__":
    bridge = ComboProximityBridge()
    bridge.run()