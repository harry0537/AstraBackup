#!/usr/bin/env python3
"""
Fixed Combo Proximity Bridge - Aggressive buffer management for RPLidar S3
WORKING VERSION - Successfully tested with Mission Planner proximity display
"""

import time
import sys
import numpy as np
import threading
from rplidar import RPLidar
from pymavlink import mavutil

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

class FixedComboProximityBridge:
    def __init__(self):
        self.lidar_port = '/dev/ttyUSB0'
        self.pixhawk_port = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
        self.pixhawk_baud = 57600
        
        self.min_distance_cm = 20
        self.max_distance_cm = 2500
        self.quality_threshold = 10
        self.num_sectors = 8
        
        self.lidar = None
        self.realsense_pipeline = None
        self.mavlink = None
        
        # Data storage with thread safety
        self.lidar_sectors = [self.max_distance_cm] * self.num_sectors
        self.realsense_sectors = [self.max_distance_cm] * self.num_sectors
        self.fused_sectors = [self.max_distance_cm] * self.num_sectors
        
        # Threading for continuous lidar processing
        self.lidar_thread_running = False
        self.lidar_data_lock = threading.Lock()
        
        # Statistics
        self.lidar_success_count = 0
        self.realsense_success_count = 0
        self.total_cycles = 0
        
    def aggressive_buffer_clear(self):
        """Aggressively clear RPLidar buffers"""
        try:
            if self.lidar and hasattr(self.lidar, '_serial') and self.lidar._serial:
                serial_conn = self.lidar._serial
                
                # Multiple buffer clearing attempts
                for _ in range(3):
                    serial_conn.reset_input_buffer()
                    serial_conn.reset_output_buffer()
                    time.sleep(0.05)
                
                # Drain any remaining data
                while serial_conn.in_waiting > 0:
                    try:
                        serial_conn.read(serial_conn.in_waiting)
                    except:
                        break
                    time.sleep(0.01)
                    
        except Exception as e:
            print(f"Buffer clear error: {e}")
    
    def connect_devices(self):
        try:
            print("Connecting to Pixhawk...")
            self.mavlink = mavutil.mavlink_connection(
                self.pixhawk_port,
                baud=self.pixhawk_baud,
                source_system=1,
                source_component=195
            )
            
            self.mavlink.wait_heartbeat(timeout=10)
            print("Pixhawk connected")
            
            success_lidar = self.connect_rplidar()
            success_realsense = self.connect_realsense()
            
            if not success_lidar and not success_realsense:
                print("ERROR: No sensors connected")
                return False
            
            return True
            
        except Exception as e:
            print(f"Device connection failed: {e}")
            return False
    
    def connect_rplidar(self):
        try:
            print("Connecting RPLidar S3...")
            self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=0.1)
            
            # Aggressive initial buffer clearing
            self.aggressive_buffer_clear()
            
            info = self.lidar.get_info()
            health = self.lidar.get_health()
            
            print(f"RPLidar connected - Model: {info['model']}, Health: {health[0]}")
            return True
            
        except Exception as e:
            print(f"RPLidar connection failed: {e}")
            self.lidar = None
            return False
    
    def connect_realsense(self):
        if not REALSENSE_AVAILABLE:
            return False
            
        try:
            print("Connecting RealSense camera...")
            
            self.realsense_pipeline = rs.pipeline()
            config = rs.config()
            
            # Lower resolution for better performance
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 15)  # Reduced to 15fps
            
            self.realsense_pipeline.start(config)
            
            # Warm up
            for _ in range(5):
                self.realsense_pipeline.wait_for_frames()
            
            print("RealSense connected successfully")
            return True
            
        except Exception as e:
            print(f"RealSense connection failed: {e}")
            self.realsense_pipeline = None
            return False
    
    def lidar_continuous_thread(self):
        """Continuous RPLidar processing in background thread"""
        print("Starting RPLidar background thread...")
        
        buffer_clear_interval = 0
        
        while self.lidar_thread_running:
            try:
                # Clear buffers every few iterations
                buffer_clear_interval += 1
                if buffer_clear_interval >= 5:
                    self.aggressive_buffer_clear()
                    buffer_clear_interval = 0
                
                # Start motor
                self.lidar.start_motor()
                time.sleep(0.3)  # Short stabilization
                
                # Collect data quickly
                scan_data = []
                measurement_count = 0
                start_time = time.time()
                
                for measurement in self.lidar.iter_measurments():
                    if not self.lidar_thread_running:
                        break
                        
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                        
                        if quality >= self.quality_threshold and distance > 0:
                            scan_data.append((quality, angle, distance))
                    
                    measurement_count += 1
                    
                    # Quick exit - get data fast to prevent buffer buildup
                    if len(scan_data) > 20 and time.time() - start_time > 0.5:
                        break
                        
                    if measurement_count > 200 or time.time() - start_time > 1.0:
                        break
                
                # Process to sectors if we got data
                if len(scan_data) > 10:
                    sectors = [self.max_distance_cm] * self.num_sectors
                    
                    for quality, angle, distance_mm in scan_data:
                        distance_cm = max(self.min_distance_cm, 
                                        min(int(distance_mm / 10), self.max_distance_cm))
                        
                        sector = int((angle + 22.5) / 45) % 8
                        
                        if distance_cm < sectors[sector]:
                            sectors[sector] = distance_cm
                    
                    # Thread-safe update
                    with self.lidar_data_lock:
                        self.lidar_sectors = sectors
                
                # Stop motor to prevent buffer buildup
                try:
                    self.lidar.stop()
                except:
                    pass
                
                time.sleep(0.2)  # Brief pause between scans
                
            except Exception as e:
                print(f"Lidar thread error: {e}")
                self.aggressive_buffer_clear()
                time.sleep(0.5)
    
    def get_realsense_data(self):
        """Get RealSense sector data"""
        if not self.realsense_pipeline:
            return False
            
        try:
            frames = self.realsense_pipeline.wait_for_frames(timeout_ms=500)
            depth_frame = frames.get_depth_frame()
            
            if not depth_frame:
                return False
            
            depth_image = np.asanyarray(depth_frame.get_data())
            height, width = depth_image.shape
            
            sectors = [self.max_distance_cm] * self.num_sectors
            
            # Process forward regions only (where RealSense is most useful)
            regions = [
                (height//3, 2*height//3, width//3, 2*width//3),      # Forward center
                (height//3, 2*height//3, 2*width//3, width),        # Forward right  
                (height//3, 2*height//3, 0, width//3),              # Forward left
            ]
            
            forward_sectors = [0, 1, 7]
            
            for i, (y1, y2, x1, x2) in enumerate(regions):
                region = depth_image[y1:y2, x1:x2]
                valid_region = region[0:2*(y2-y1)//3, :]
                valid_depths = valid_region[(valid_region > 100) & (valid_region < 5000)]
                
                if len(valid_depths) > 10:
                    closest_mm = np.percentile(valid_depths, 5)
                    closest_cm = max(self.min_distance_cm, 
                                   min(int(closest_mm / 10), self.max_distance_cm))
                    
                    sectors[forward_sectors[i]] = closest_cm
            
            self.realsense_sectors = sectors
            return True
            
        except Exception as e:
            print(f"RealSense error: {e}")
            return False
    
    def fuse_sensor_data(self):
        """Combine RPLidar and RealSense data intelligently"""
        # Get current lidar data thread-safely
        with self.lidar_data_lock:
            current_lidar_sectors = self.lidar_sectors.copy()
        
        fused = [self.max_distance_cm] * self.num_sectors
        
        for i in range(self.num_sectors):
            lidar_dist = current_lidar_sectors[i]
            realsense_dist = self.realsense_sectors[i]
            
            # Forward sectors: prefer RealSense
            if i in [0, 1, 7]:
                if realsense_dist < self.max_distance_cm:
                    fused[i] = realsense_dist
                elif lidar_dist < self.max_distance_cm:
                    fused[i] = lidar_dist
            # Other sectors: prefer RPLidar
            else:
                if lidar_dist < self.max_distance_cm:
                    fused[i] = lidar_dist
                elif realsense_dist < self.max_distance_cm:
                    fused[i] = realsense_dist
        
        self.fused_sectors = fused
    
    def send_proximity_data(self, sector_distances):
        """Send DISTANCE_SENSOR messages to Pixhawk"""
        try:
            timestamp = int(time.time() * 1000) & 0xFFFFFFFF
            orientations = [0, 2, 2, 4, 4, 6, 6, 0]
            
            for sector_id, distance in enumerate(sector_distances):
                self.mavlink.mav.distance_sensor_send(
                    time_boot_ms=timestamp,
                    min_distance=self.min_distance_cm,
                    max_distance=self.max_distance_cm,
                    current_distance=distance,
                    type=1,
                    id=sector_id,
                    orientation=orientations[sector_id],
                    covariance=0
                )
        except Exception as e:
            print(f"MAVLink send error: {e}")
    
    def run(self):
        """Main processing loop"""
        if not self.connect_devices():
            return False
        
        print("\nFixed Combo Proximity Bridge running...")
        print("Aggressive buffer management for RPLidar S3")
        print("Press Ctrl+C to stop\n")
        
        # Start RPLidar background thread
        if self.lidar:
            self.lidar_thread_running = True
            lidar_thread = threading.Thread(target=self.lidar_continuous_thread, daemon=True)
            lidar_thread.start()
        
        try:
            while True:
                self.total_cycles += 1
                
                # RealSense processing (main thread)
                realsense_success = self.get_realsense_data()
                if realsense_success:
                    self.realsense_success_count += 1
                
                # Check if we have recent lidar data
                lidar_success = False
                with self.lidar_data_lock:
                    if any(d < self.max_distance_cm for d in self.lidar_sectors):
                        lidar_success = True
                        self.lidar_success_count += 1
                
                # Fuse and send data
                self.fuse_sensor_data()
                self.send_proximity_data(self.fused_sectors)
                
                # Status
                obstacles = sum(1 for d in self.fused_sectors if d < self.max_distance_cm)
                closest = min(self.fused_sectors)
                
                lidar_rate = (self.lidar_success_count / self.total_cycles) * 100
                realsense_rate = (self.realsense_success_count / self.total_cycles) * 100
                
                status = f"Cycle {self.total_cycles}: {obstacles}/8 sectors, {closest}cm"
                status += f" | L:{lidar_rate:.0f}% R:{realsense_rate:.0f}%"
                
                if lidar_success and realsense_success:
                    print(f"BOTH {status}")
                elif realsense_success:
                    print(f"REAL {status}")
                elif lidar_success:
                    print(f"LIDAR {status}")
                else:
                    print(f"NONE {status}")
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print(f"\nStopping...")
        finally:
            self.lidar_thread_running = False
            self.cleanup()
    
    def cleanup(self):
        """Clean shutdown"""
        self.lidar_thread_running = False
        
        if self.lidar:
            try:
                self.lidar.stop()
                self.lidar.disconnect()
                print("RPLidar disconnected")
            except:
                pass
                
        if self.realsense_pipeline:
            try:
                self.realsense_pipeline.stop()
                print("RealSense disconnected")
            except:
                pass
                
        if self.mavlink:
            try:
                self.mavlink.close()
                print("Pixhawk disconnected")
            except:
                pass

if __name__ == "__main__":
    bridge = FixedComboProximityBridge()
    bridge.run()
