#!/usr/bin/env python3
"""
Project Astra NZ - Proximity Bridge v5
Fixed: LiDAR start_scan parameter and MAVLink value validation
Combines RPLidar S3 and RealSense for 8-sector proximity detection
"""

import time
import math
import threading
import queue
from typing import Optional, Tuple, Dict
import os
import sys

try:
    from rplidar import RPLidar
    RPLIDAR_AVAILABLE = True
except ImportError:
    print("RPLidar library not available")
    RPLIDAR_AVAILABLE = False

try:
    import pyrealsense2 as rs
    import numpy as np
    REALSENSE_AVAILABLE = True
except ImportError:
    print("RealSense library not available")
    REALSENSE_AVAILABLE = False

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    print("MAVLink library not available")
    MAVLINK_AVAILABLE = False


class ProximityBridge:
    def __init__(self):
        # Hardware configuration
        self.lidar_port = '/dev/ttyUSB0'
        self.pixhawk_port = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
        self.pixhawk_baud = 57600
        
        # 8 sectors: N, NE, E, SE, S, SW, W, NW (45° each)
        self.sector_angles = [0, 45, 90, 135, 180, 225, 270, 315]
        self.distances = [25.0] * 8  # Initialize to max range
        
        # Performance tracking
        self.lidar_success = 0
        self.lidar_total = 0
        self.realsense_success = 0
        self.realsense_total = 0
        
        # Thread coordination
        self.running = True
        self.data_lock = threading.Lock()
        self.lidar_queue = queue.Queue(maxsize=50)
        
        # Initialize hardware
        self.lidar = None
        self.mavlink = None
        self.realsense_pipeline = None
        
        # Error tracking
        self.lidar_error_count = 0
        self.max_lidar_errors = 5

    def validate_distance(self, distance: float) -> float:
        """Ensure distance values are within valid MAVLink range"""
        if distance is None or math.isnan(distance) or math.isinf(distance):
            return 25.0  # Max range fallback
        
        # Clamp to valid range for MAVLink DISTANCE_SENSOR (0 to 65535 cm)
        distance_cm = max(20.0, min(distance * 100, 6553.5))  # Convert to cm and clamp
        return distance_cm / 100.0  # Convert back to meters

    def init_lidar(self) -> bool:
        """Initialize RPLidar S3"""
        if not RPLIDAR_AVAILABLE:
            print("RPLidar library not available")
            return False
            
        try:
            if not os.path.exists(self.lidar_port):
                print(f"LiDAR port {self.lidar_port} not found")
                return False
                
            print(f"Connecting to LiDAR at {self.lidar_port}...")
            self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=2)
            
            # Get device info
            info = self.lidar.get_info()
            health = self.lidar.get_health()
            print(f"LiDAR connected - Model: {info['model']}, Health: {health[0]}")
            
            # Start scanning with express mode
            self.lidar.start_scan(scan_type='express')
            print("LiDAR scanning started (express mode)")
            return True
            
        except Exception as e:
            print(f"LiDAR initialization failed: {e}")
            if self.lidar:
                try:
                    self.lidar.disconnect()
                except:
                    pass
                self.lidar = None
            return False

    def init_realsense(self) -> bool:
        """Initialize RealSense D435i"""
        if not REALSENSE_AVAILABLE:
            print("RealSense library not available")
            return False
            
        try:
            self.realsense_pipeline = rs.pipeline()
            config = rs.config()
            
            config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
            
            profile = self.realsense_pipeline.start(config)
            
            # Get depth scale
            depth_sensor = profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            
            print("RealSense initialized - depth stream active")
            return True
            
        except Exception as e:
            print(f"RealSense initialization failed: {e}")
            if self.realsense_pipeline:
                try:
                    self.realsense_pipeline.stop()
                except:
                    pass
                self.realsense_pipeline = None
            return False

    def init_mavlink(self) -> bool:
        """Initialize MAVLink connection"""
        if not MAVLINK_AVAILABLE:
            print("MAVLink library not available")
            return False
            
        try:
            # Try by-id path first, fallback to ttyACM
            if os.path.exists(self.pixhawk_port):
                connection_string = self.pixhawk_port
            else:
                # Fallback to ttyACM0
                connection_string = '/dev/ttyACM0'
                
            print(f"Connecting to Pixhawk at {connection_string}...")
            self.mavlink = mavutil.mavlink_connection(
                connection_string, 
                baud=self.pixhawk_baud
            )
            
            # Wait for heartbeat
            self.mavlink.wait_heartbeat(timeout=10)
            print("MAVLink connection established")
            return True
            
        except Exception as e:
            print(f"MAVLink initialization failed: {e}")
            self.mavlink = None
            return False

    def restart_lidar(self):
        """Restart LiDAR connection after errors"""
        print("Restarting LiDAR connection...")
        
        if self.lidar:
            try:
                self.lidar.stop_scan()
                self.lidar.disconnect()
            except:
                pass
            self.lidar = None
            
        time.sleep(2)
        
        if self.init_lidar():
            self.lidar_error_count = 0
            print("LiDAR restart successful")
        else:
            print("LiDAR restart failed")

    def lidar_thread(self):
        """LiDAR data collection thread with buffer management"""
        while self.running:
            if not self.lidar:
                time.sleep(1)
                continue
                
            try:
                # Process scan data with buffer clearing
                scan_data = []
                for i, scan in enumerate(self.lidar.iter_scans()):
                    if not self.running:
                        break
                        
                    scan_data = list(scan)
                    
                    # Clear old data from queue
                    while not self.lidar_queue.empty():
                        try:
                            self.lidar_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    # Add new data
                    try:
                        self.lidar_queue.put(scan_data, block=False)
                    except queue.Full:
                        pass
                    
                    # Process every 5 scans to reduce CPU load
                    if i % 5 == 0:
                        break
                        
                self.lidar_error_count = 0  # Reset on successful read
                
            except Exception as e:
                self.lidar_error_count += 1
                print(f"LiDAR error ({self.lidar_error_count}/{self.max_lidar_errors}): {e}")
                
                if self.lidar_error_count >= self.max_lidar_errors:
                    print("Too many consecutive LiDAR errors, restarting connection...")
                    self.restart_lidar()
                
                time.sleep(0.1)

    def process_lidar_data(self, scan_data) -> Dict[str, float]:
        """Convert LiDAR scan to 8-sector distances"""
        sector_distances = {}
        
        for angle_deg, distance_mm, quality in scan_data:
            if quality < 10:  # Skip low quality readings
                continue
                
            distance_m = self.validate_distance(distance_mm / 1000.0)
            
            # Determine sector (0=N, 1=NE, 2=E, etc.)
            sector_idx = int((angle_deg + 22.5) / 45) % 8
            sector_name = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][sector_idx]
            
            # Keep minimum distance for each sector
            if sector_name not in sector_distances or distance_m < sector_distances[sector_name]:
                sector_distances[sector_name] = distance_m
                
        return sector_distances

    def get_realsense_forward_distance(self) -> float:
        """Get forward distance from RealSense"""
        if not self.realsense_pipeline:
            return 25.0
            
        try:
            frames = self.realsense_pipeline.wait_for_frames(timeout_ms=100)
            depth_frame = frames.get_depth_frame()
            
            if not depth_frame:
                return 25.0
                
            # Get depth data as numpy array
            depth_data = np.asanyarray(depth_frame.get_data())
            height, width = depth_data.shape
            
            # Sample center region (avoid edges)
            center_y = height // 2
            center_x = width // 2
            region_size = 50
            
            y1 = max(0, center_y - region_size)
            y2 = min(height, center_y + region_size)
            x1 = max(0, center_x - region_size)
            x2 = min(width, center_x + region_size)
            
            center_region = depth_data[y1:y2, x1:x2]
            
            # Filter out zeros and convert to meters
            valid_depths = center_region[center_region > 0] * self.depth_scale
            
            if len(valid_depths) > 0:
                # Use median of valid depths for robustness
                distance = float(np.median(valid_depths))
                return self.validate_distance(distance)
            else:
                return 25.0
                
        except Exception:
            return 25.0

    def update_distances(self):
        """Update proximity distances from all sensors"""
        # Start with max range for all sectors
        new_distances = [25.0] * 8
        
        # Update from LiDAR if available
        lidar_updated = False
        if not self.lidar_queue.empty():
            try:
                scan_data = self.lidar_queue.get_nowait()
                self.lidar_total += 1
                
                sector_distances = self.process_lidar_data(scan_data)
                
                # Map to distance array (skip forward sector for RealSense)
                sector_map = {
                    'NE': 1, 'E': 2, 'SE': 3, 'S': 4, 'SW': 5, 'W': 6, 'NW': 7
                }
                
                for sector_name, distance in sector_distances.items():
                    if sector_name in sector_map:
                        new_distances[sector_map[sector_name]] = distance
                        
                self.lidar_success += 1
                lidar_updated = True
                
            except queue.Empty:
                pass
        
        if not lidar_updated:
            self.lidar_total += 1
        
        # Update forward (North) from RealSense
        self.realsense_total += 1
        forward_distance = self.get_realsense_forward_distance()
        if forward_distance < 25.0:
            new_distances[0] = forward_distance
            self.realsense_success += 1
        
        # Thread-safe update
        with self.data_lock:
            self.distances = new_distances

    def send_proximity_data(self):
        """Send proximity data via MAVLink"""
        if not self.mavlink:
            return
            
        with self.data_lock:
            current_distances = self.distances.copy()
        
        try:
            # Convert to centimeters and ensure valid range
            distances_cm = []
            for dist in current_distances:
                dist_cm = int(self.validate_distance(dist) * 100)
                # Ensure within MAVLink range (0-65535)
                dist_cm = max(20, min(dist_cm, 6553))
                distances_cm.append(dist_cm)
            
            self.mavlink.mav.distance_sensor_send(
                time_boot_ms=int(time.time() * 1000) % (2**32),  # Prevent overflow
                min_distance=20,    # 20cm minimum
                max_distance=6553,  # 65.53m maximum  
                current_distance=distances_cm[0],  # Forward distance
                type=0,  # Laser
                id=195,  # Component ID for proximity sensor
                orientation=0,  # Forward facing
                covariance=255,  # Unknown variance
                horizontal_fov=6.28,  # 360 degrees in radians
                vertical_fov=0.26,    # ~15 degrees in radians
                quaternion=[1.0, 0.0, 0.0, 0.0],  # No rotation
                signal_quality=100,
                distances=distances_cm
            )
            
        except Exception as e:
            print(f"MAVLink transmission error: {e}")

    def print_status(self):
        """Print system status"""
        with self.data_lock:
            current_distances = self.distances.copy()
        
        lidar_rate = (self.lidar_success / max(1, self.lidar_total)) * 100
        realsense_rate = (self.realsense_success / max(1, self.realsense_total)) * 100
        
        print("=" * 60)
        print(f"System Status - {time.strftime('%H:%M:%S')}")
        print("=" * 60)
        print(f"LiDAR:       {self.lidar_success:4}/{self.lidar_total:4} ({lidar_rate:5.1f}%)")
        print(f"RealSense:   {self.realsense_success:4}/{self.realsense_total:4} ({realsense_rate:5.1f}%)")
        
        print("Proximity Data (meters):")
        sectors = ['N ', 'NE', 'E ', 'SE', 'S ', 'SW', 'W ', 'NW']
        for i, (sector, distance) in enumerate(zip(sectors, current_distances)):
            print(f"  {sector}: {distance:5.2f}m")

    def cleanup(self):
        """Cleanup all resources"""
        print("\nShutting down...")
        self.running = False
        
        if self.lidar:
            try:
                self.lidar.stop_scan()
                self.lidar.disconnect()
                print("LiDAR disconnected")
            except:
                pass
                
        if self.realsense_pipeline:
            try:
                self.realsense_pipeline.stop()
                print("RealSense stopped")
            except:
                pass
                
        if self.mavlink:
            try:
                self.mavlink.close()
                print("MAVLink disconnected")
            except:
                pass

    def run(self):
        """Main execution loop"""
        print("Project Astra NZ - Proximity Bridge v5")
        print("Initializing sensors...")
        
        # Initialize hardware
        mavlink_ok = self.init_mavlink()
        lidar_ok = self.init_lidar()
        realsense_ok = self.init_realsense()
        
        if not mavlink_ok:
            print("MAVLink required for operation")
            return
            
        if not (lidar_ok or realsense_ok):
            print("At least one sensor required")
            return
        
        # Start LiDAR thread
        if lidar_ok:
            lidar_thread = threading.Thread(target=self.lidar_thread, daemon=True)
            lidar_thread.start()
        
        # Main loop
        last_status = time.time()
        
        try:
            while True:
                start_time = time.time()
                
                # Update sensor data
                self.update_distances()
                
                # Send to ArduPilot
                self.send_proximity_data()
                
                # Status display
                if time.time() - last_status >= 30:
                    self.print_status()
                    last_status = time.time()
                
                # Maintain 2Hz update rate
                elapsed = time.time() - start_time
                sleep_time = max(0, 0.5 - elapsed)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()


if __name__ == "__main__":
    bridge = ProximityBridge()
    bridge.run()
