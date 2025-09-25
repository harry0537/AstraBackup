#!/usr/bin/env python3
"""
Simple Obstacle Avoidance - RPLidar + RealSense -> Pixhawk
Focus: Just get sensor data and send to Pixhawk for obstacle avoidance
"""

import time
import threading
import numpy as np
from rplidar import RPLidar
from pymavlink import mavutil
import os

# RealSense optional
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

class SimpleObstacleAvoidance:
    def __init__(self):
        self.lidar = None
        self.mavlink = None
        self.pipeline = None
        self.running = True
        
        # 8 sectors for obstacle avoidance
        self.num_sectors = 8
        self.min_distance_cm = 20
        self.max_distance_cm = 1000  # 10m max for obstacle avoidance
        
        # Sensor data
        self.sectors = [self.max_distance_cm] * self.num_sectors
        self.lock = threading.Lock()
        
        # Stats
        self.lidar_count = 0
        self.realsense_count = 0
        self.messages_sent = 0

    def connect_pixhawk(self):
        """Connect to Pixhawk - try multiple ports"""
        ports = ['/dev/pixhawk', '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2']
        
        for port in ports:
            try:
                if os.path.exists(port):
                    print(f"Connecting to Pixhawk at {port}...")
                    self.mavlink = mavutil.mavlink_connection(port, baud=57600)
                    self.mavlink.wait_heartbeat(timeout=3)
                    print(f"✓ Pixhawk connected at {port}")
                    return True
            except Exception as e:
                print(f"✗ Failed {port}: {e}")
                continue
        return False

    def connect_lidar(self):
        """Connect to RPLidar - simple approach"""
        ports = ['/dev/rplidar', '/dev/ttyUSB0', '/dev/ttyUSB1']
        
        for port in ports:
            try:
                if os.path.exists(port):
                    print(f"Connecting to RPLidar at {port}...")
                    self.lidar = RPLidar(port, baudrate=1000000, timeout=0.1)
                    print(f"✓ RPLidar connected at {port}")
                    return True
            except Exception as e:
                print(f"✗ Failed {port}: {e}")
                continue
        return False

    def connect_realsense(self):
        """Connect to RealSense - with device release"""
        if not REALSENSE_AVAILABLE:
            return False
            
        try:
            print("Connecting to RealSense...")
            
            # Release device first
            try:
                import subprocess
                subprocess.run(['sudo', 'fuser', '-k', '/dev/video*'], capture_output=True)
                time.sleep(1.0)
            except:
                pass
            
            self.pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, 320, 240, rs.format.z16, 15)
            self.pipeline.start(config)
            
            # Warm up
            for _ in range(3):
                self.pipeline.wait_for_frames()
            
            print("✓ RealSense connected")
            return True
        except Exception as e:
            print(f"✗ RealSense failed: {e}")
            return False

    def lidar_worker(self):
        """LiDAR data collection - simple and robust"""
        while self.running:
            if not self.lidar:
                time.sleep(0.5)
                continue
                
            try:
                # Start motor
                self.lidar.start_motor()
                time.sleep(0.2)
                
                # Collect data quickly
                sectors = [self.max_distance_cm] * self.num_sectors
                count = 0
                
                for measurement in self.lidar.iter_measurments():
                    if not self.running or count > 100:
                        break
                        
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                        if quality > 10 and distance > 0:
                            # Convert to cm and map to sector
                            distance_cm = min(int(distance / 10), self.max_distance_cm)
                            sector = int((angle + 22.5) / 45) % 8
                            
                            if distance_cm < sectors[sector]:
                                sectors[sector] = distance_cm
                    count += 1
                
                # Update global sectors
                with self.lock:
                    for i in range(self.num_sectors):
                        if sectors[i] < self.sectors[i]:
                            self.sectors[i] = sectors[i]
                    self.lidar_count += 1
                
                # Stop motor
                self.lidar.stop()
                time.sleep(0.3)
                
            except Exception as e:
                print(f"LiDAR error: {e}")
                time.sleep(0.5)

    def realsense_worker(self):
        """RealSense data collection - simple forward detection"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue
                
            try:
                frames = self.pipeline.wait_for_frames()
                depth_frame = frames.get_depth_frame()
                
                if depth_frame:
                    # Sample center region for forward obstacles
                    width = depth_frame.get_width()
                    height = depth_frame.get_height()
                    center_x, center_y = width // 2, height // 2
                    
                    # Sample 10x10 grid in center
                    min_distance = self.max_distance_cm
                    for i in range(10):
                        for j in range(10):
                            x = center_x - 5 + i
                            y = center_y - 5 + j
                            if 0 <= x < width and 0 <= y < height:
                                d = depth_frame.get_distance(x, y)
                                if 0.2 < d < 5.0:  # 20cm to 5m
                                    distance_cm = int(d * 100)
                                    if distance_cm < min_distance:
                                        min_distance = distance_cm
                    
                    # Update forward sectors (0, 1, 7)
                    if min_distance < self.max_distance_cm:
                        with self.lock:
                            for sector in [0, 1, 7]:
                                if min_distance < self.sectors[sector]:
                                    self.sectors[sector] = min_distance
                            self.realsense_count += 1
                
            except Exception:
                time.sleep(0.1)

    def send_to_pixhawk(self):
        """Send proximity data to Pixhawk for obstacle avoidance"""
        if not self.mavlink:
            return
            
        with self.lock:
            sectors = self.sectors.copy()
        
        # Send 8 sectors to Pixhawk
        orientations = [0, 2, 2, 4, 4, 6, 6, 0]  # MAVLink orientations
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        
        for sector_id, distance_cm in enumerate(sectors):
            try:
                self.mavlink.mav.distance_sensor_send(
                    time_boot_ms=timestamp,
                    min_distance=self.min_distance_cm,
                    max_distance=self.max_distance_cm,
                    current_distance=int(distance_cm),
                    type=1,  # Generic distance sensor
                    id=sector_id,
                    orientation=orientations[sector_id],
                    covariance=0
                )
            except Exception:
                pass
        
        self.messages_sent += self.num_sectors

    def print_status(self):
        """Print current status"""
        with self.lock:
            min_dist = min(self.sectors) if self.sectors else self.max_distance_cm
            sectors_str = [f"{s/100:.1f}" for s in self.sectors]
        
        print(f"\rL:{self.lidar_count:3d} R:{self.realsense_count:3d} "
              f"Sent:{self.messages_sent:4d} Min:{min_dist/100:.1f}m "
              f"Sectors:[{','.join(sectors_str)}]", end='')

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Simple Obstacle Avoidance - RPLidar + RealSense -> Pixhawk")
        print("=" * 60)
        
        # Connect hardware
        if not self.connect_pixhawk():
            print("❌ Cannot connect to Pixhawk")
            return
            
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense()
        
        if not lidar_ok and not realsense_ok:
            print("❌ No sensors available")
            return
            
        print(f"\n✓ Hardware ready - LiDAR:{lidar_ok} RealSense:{realsense_ok}")
        print("Sending 8-sector proximity data to Pixhawk for obstacle avoidance")
        print("Press Ctrl+C to stop\n")
        
        # Start worker threads
        if lidar_ok:
            lidar_thread = threading.Thread(target=self.lidar_worker, daemon=True)
            lidar_thread.start()
            
        if realsense_ok:
            rs_thread = threading.Thread(target=self.realsense_worker, daemon=True)
            rs_thread.start()
        
        # Main loop
        try:
            last_send = time.time()
            last_status = time.time()
            
            while self.running:
                # Send data to Pixhawk at 10Hz
                if time.time() - last_send > 0.1:
                    self.send_to_pixhawk()
                    last_send = time.time()
                
                # Print status at 1Hz
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\nStopping obstacle avoidance...")
            
        finally:
            self.running = False
            
            # Cleanup
            if self.lidar:
                try:
                    self.lidar.stop()
                    self.lidar.disconnect()
                except:
                    pass
                    
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
            
            print("✓ Obstacle avoidance stopped")

if __name__ == "__main__":
    obstacle_avoidance = SimpleObstacleAvoidance()
    obstacle_avoidance.run()
