#!/usr/bin/env python3
"""
Project Astra NZ - Integrated Proximity & Data Relay v5
EXACT COPY of working proximity script + minimal data relay
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

# Optional data relay imports (only if dashboard enabled)
try:
    import json
    import requests
    from datetime import datetime
    DATA_RELAY_AVAILABLE = True
except ImportError:
    DATA_RELAY_AVAILABLE = False

class IntegratedProximityRelay:
    def __init__(self, enable_dashboard=False, dashboard_url="http://10.244.77.186:8080"):
        # EXACT COPY FROM WORKING SCRIPT
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
        
        # EXACT COPY: Data storage with thread safety
        self.lidar_sectors = [self.max_distance_cm] * self.num_sectors
        self.realsense_sectors = [self.max_distance_cm] * self.num_sectors
        self.fused_sectors = [self.max_distance_cm] * self.num_sectors
        
        # EXACT COPY: Threading for continuous lidar processing
        self.lidar_thread_running = False
        self.lidar_data_lock = threading.Lock()
        
        # EXACT COPY: Statistics
        self.lidar_success_count = 0
        self.realsense_success_count = 0
        self.total_cycles = 0
        
        # DATA RELAY (minimal addition)
        self.enable_dashboard = enable_dashboard and DATA_RELAY_AVAILABLE
        self.dashboard_url = dashboard_url
        self.relay_data = []
        
        print("Project Astra NZ - Integrated Proximity & Data Relay v5")
        print("EXACT copy of working proximity script")
        if self.enable_dashboard:
            print(f"Data relay: {dashboard_url}")
        else:
            print("Data relay: DISABLED")
        print("=" * 60)
    
    def aggressive_buffer_clear(self):
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script + minimal data collection"""
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
                    
                    # MINIMAL DATA COLLECTION - every 20th scan
                    if self.enable_dashboard and measurement_count % 20 == 0:
                        self.collect_data_sample('lidar', scan_data[:5])  # Just 5 points
                
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
        """EXACT COPY from working script + minimal data collection"""
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
            
            # MINIMAL DATA COLLECTION - every 50th call  
            if self.enable_dashboard and self.total_cycles % 50 == 0:
                center_region = depth_image[height//3:2*height//3, width//3:2*width//3]
                valid_depths = center_region[(center_region > 100) & (center_region < 5000)]
                if len(valid_depths) > 10:
                    self.collect_data_sample('camera', {
                        'min': int(np.min(valid_depths)),
                        'avg': int(np.mean(valid_depths)),
                        'pixels': len(valid_depths)
                    })
            
            return True
            
        except Exception as e:
            print(f"RealSense error: {e}")
            return False
    
    def collect_data_sample(self, sensor_type, data):
        """Minimal data collection for relay"""
        if not self.enable_dashboard:
            return
            
        sample = {
            'type': sensor_type,
            'time': time.time(),
            'data': data
        }
        
        self.relay_data.append(sample)
        
        # Keep only last 20 samples
        if len(self.relay_data) > 20:
            self.relay_data = self.relay_data[-20:]
    
    def send_data_to_dashboard(self):
        """Send collected data to dashboard"""
        if not self.enable_dashboard or not self.relay_data:
            return
            
        try:
            payload = {
                'rover_id': 'astra_nz',
                'timestamp': datetime.now().isoformat(),
                'samples': self.relay_data
            }
            
            response = requests.post(
                f"{self.dashboard_url}/api/rover_data",
                json=payload,
                timeout=2
            )
            
            if response.status_code == 200:
                self.relay_data = []  # Clear sent data
                
        except Exception as e:
            print(f"Dashboard error: {e}")
    
    def fuse_sensor_data(self):
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script"""
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
        """EXACT COPY from working script + minimal dashboard calls"""
        if not self.connect_devices():
            return False
        
        print("\nIntegrated Proximity & Data Relay running...")
        print("Exact copy of working proximity + minimal data relay")
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
                
                # MINIMAL dashboard send (every 100 cycles)
                if self.enable_dashboard and self.total_cycles % 100 == 0:
                    self.send_data_to_dashboard()
                
                # Status
                obstacles = sum(1 for d in self.fused_sectors if d < self.max_distance_cm)
                closest = min(self.fused_sectors)
                
                lidar_rate = (self.lidar_success_count / self.total_cycles) * 100
                realsense_rate = (self.realsense_success_count / self.total_cycles) * 100
                
                status = f"Cycle {self.total_cycles}: {obstacles}/8 sectors, {closest}cm"
                status += f" | L:{lidar_rate:.0f}% R:{realsense_rate:.0f}%"
                
                if self.enable_dashboard:
                    status += f" | Data:{len(self.relay_data)}"
                
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
        """EXACT COPY from working script"""
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Integrated Proximity & Data Relay v5')
    parser.add_argument('--dashboard', action='store_true', help='Enable dashboard relay')
    parser.add_argument('--url', default='http://10.244.77.186:8080', help='Dashboard URL')
    
    args = parser.parse_args()
    
    bridge = IntegratedProximityRelay(
        enable_dashboard=args.dashboard,
        dashboard_url=args.url
    )
    bridge.run()
