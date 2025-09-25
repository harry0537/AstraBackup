#!/usr/bin/env python3
"""
Simple Proximity Bridge V4 - Bypass problematic RPLidar methods
RPLidar S3 + RealSense D435i -> Pixhawk 6C (8 sectors)
"""

import time
import threading
import numpy as np
from rplidar import RPLidar
from pymavlink import mavutil
import json
import os

# RealSense is optional
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except Exception:
    REALSENSE_AVAILABLE = False

# Device paths
LIDAR_PORT = '/dev/rplidar'
PIXHAWK_PORT = '/dev/pixhawk'
PIXHAWK_BAUD = 57600
COMPONENT_ID = 195

class SimpleProximityBridge:
    def __init__(self):
        self.lidar = None
        self.mavlink = None
        self.pipeline = None
        self.running = True
        
        # Proximity configuration (cm)
        self.min_distance_cm = 20
        self.max_distance_cm = 2500
        self.quality_threshold = 10
        self.num_sectors = 8

        # Sensor data storage
        self.lidar_sectors = [self.max_distance_cm] * self.num_sectors
        self.realsense_sectors = [self.max_distance_cm] * self.num_sectors
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'lidar_success': 0,
            'lidar_errors': 0,
            'realsense_success': 0,
            'messages_sent': 0,
            'start_time': time.time()
        }

    def connect_pixhawk(self):
        """Connect to Pixhawk with port management"""
        try:
            candidate_ports = [PIXHAWK_PORT, '/dev/ttyACM0', '/dev/ttyACM1']
            
            for port in candidate_ports:
                try:
                    print(f"  Connecting Pixhawk at {port}...")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=1,
                        source_component=COMPONENT_ID
                    )
                    self.mavlink.wait_heartbeat(timeout=3)
                    print(f"  ✓ Pixhawk connected at {port}")
                    return True
                except Exception as e:
                    print(f"  ✗ Pixhawk failed at {port}: {e}")
                    continue
            return False
        except Exception as e:
            print(f"  ✗ Pixhawk connection failed: {e}")
            return False

    def connect_lidar(self):
        """Connect to RPLidar with minimal info checking"""
        try:
            candidate_ports = [LIDAR_PORT, '/dev/ttyUSB0', '/dev/ttyUSB1']
            
            for port in candidate_ports:
                try:
                    print(f"  Connecting RPLidar at {port}...")
                    self.lidar = RPLidar(port, baudrate=1000000, timeout=0.1)
                    
                    # Skip problematic get_info() and get_health() calls
                    print(f"  ✓ RPLidar connected at {port}")
                    return True
                except Exception as e:
                    print(f"  ✗ RPLidar failed at {port}: {e}")
                    continue
            return False
        except Exception as e:
            print(f"  ✗ RPLidar connection failed: {e}")
            return False

    def connect_realsense(self):
        """Connect to RealSense with device release"""
        if not REALSENSE_AVAILABLE:
            return False
            
        try:
            print("  Connecting RealSense...")
            
            # Try to release device first
            try:
                import subprocess
                subprocess.run(['sudo', 'fuser', '-k', '/dev/video*'], capture_output=True)
                time.sleep(1.0)
            except:
                pass
            
            self.pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 15)
            self.pipeline.start(config)
            
            # Warm-up
            for _ in range(3):
                self.pipeline.wait_for_frames()
            
            print("  ✓ RealSense connected")
            return True
        except Exception as e:
            print(f"  ✗ RealSense failed: {e}")
            return False

    def lidar_thread(self):
        """Simple LiDAR data collection"""
        while self.running:
            if not self.lidar:
                time.sleep(0.5)
                continue

            try:
                # Start motor
                self.lidar.start_motor()
                time.sleep(0.2)
                
                # Collect data
                scan_data = []
                for measurement in self.lidar.iter_measurments():
                    if not self.running:
                        break
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                        if quality >= self.quality_threshold and distance > 0:
                            scan_data.append((quality, angle, distance))
                    
                    if len(scan_data) > 50:  # Limit data collection
                        break
                
                # Process to sectors
                if len(scan_data) > 5:
                    sectors = [self.max_distance_cm] * self.num_sectors
                    for _, angle, distance_mm in scan_data:
                        distance_cm = max(self.min_distance_cm, min(int(distance_mm / 10), self.max_distance_cm))
                        sector = int((angle + 22.5) / 45) % 8
                        if distance_cm < sectors[sector]:
                            sectors[sector] = distance_cm
                    
                    with self.lock:
                        self.lidar_sectors = sectors
                    self.stats['lidar_success'] += 1
                
                # Stop motor
                self.lidar.stop()
                time.sleep(0.3)
                
            except Exception as e:
                self.stats['lidar_errors'] += 1
                time.sleep(0.5)

    def realsense_thread(self):
        """Simple RealSense data collection"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue

            try:
                frames = self.pipeline.wait_for_frames()
                depth_frame = frames.get_depth_frame()
                if not depth_frame:
                    continue
                
                # Simple forward sector processing
                sectors = [self.max_distance_cm] * self.num_sectors
                width = depth_frame.get_width()
                height = depth_frame.get_height()
                
                # Sample center region for forward sectors
                center_x, center_y = width // 2, height // 2
                for i in range(10):
                    for j in range(10):
                        x = center_x - 5 + i
                        y = center_y - 5 + j
                        if 0 <= x < width and 0 <= y < height:
                            d = depth_frame.get_distance(x, y)
                            if 0.2 < d < 10.0:  # Valid range in meters
                                distance_cm = int(d * 100)
                                if distance_cm < sectors[0]:  # Forward sector
                                    sectors[0] = distance_cm
                
                with self.lock:
                    self.realsense_sectors = sectors
                self.stats['realsense_success'] += 1
                
            except Exception:
                time.sleep(0.1)

    def fuse_and_send(self):
        """Fuse and send proximity data"""
        if not self.mavlink:
            return

        with self.lock:
            lidar = self.lidar_sectors.copy()
            rs = self.realsense_sectors.copy()

        # Simple fusion - use closest distance
        fused = [self.max_distance_cm] * self.num_sectors
        for i in range(self.num_sectors):
            lidar_dist = lidar[i] if lidar[i] < self.max_distance_cm else None
            rs_dist = rs[i] if rs[i] < self.max_distance_cm else None
            
            if lidar_dist and rs_dist:
                fused[i] = min(lidar_dist, rs_dist)
            elif lidar_dist:
                fused[i] = lidar_dist
            elif rs_dist:
                fused[i] = rs_dist

        # Send to Pixhawk
        orientations = [0, 2, 2, 4, 4, 6, 6, 0]
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        
        for sector_id, distance_cm in enumerate(fused):
            try:
                self.mavlink.mav.distance_sensor_send(
                    time_boot_ms=timestamp,
                    min_distance=self.min_distance_cm,
                    max_distance=self.max_distance_cm,
                    current_distance=int(distance_cm),
                    type=1,
                    id=sector_id,
                    orientation=orientations[sector_id],
                    covariance=0
                )
            except Exception:
                pass

        self.stats['messages_sent'] += self.num_sectors

    def print_status(self):
        """Print status"""
        uptime = int(time.time() - self.stats['start_time'])
        with self.lock:
            lidar_min = min(self.lidar_sectors) if self.lidar_sectors else self.max_distance_cm
            rs_min = min(self.realsense_sectors) if self.realsense_sectors else self.max_distance_cm
        
        print(f"\r[{uptime:3d}s] L:{self.stats['lidar_success']:3d} R:{self.stats['realsense_success']:3d} "
              f"Sent:{self.stats['messages_sent']:4d} Min:L={lidar_min/100:.1f}m R={rs_min/100:.1f}m", end='')

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Simple Proximity Bridge V4")
        print("RPLidar S3 + RealSense D435i -> Pixhawk 6C (8 sectors)")
        print("=" * 60)
        
        print("Connecting to hardware...")
        
        # Connect all systems
        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense() if REALSENSE_AVAILABLE else False
        
        if not pixhawk_ok:
            print("❌ Cannot continue without Pixhawk")
            return
            
        if not lidar_ok and not realsense_ok:
            print("❌ No sensors available")
            return
            
        print("\n✓ Hardware connected, starting threads...")
        
        # Start threads
        if lidar_ok:
            lidar_thread = threading.Thread(target=self.lidar_thread)
            lidar_thread.daemon = True
            lidar_thread.start()
            
        if realsense_ok:
            rs_thread = threading.Thread(target=self.realsense_thread)
            rs_thread.daemon = True
            rs_thread.start()
            
        print("✓ Proximity bridge operational")
        print("Press Ctrl+C to stop\n")
        
        # Main loop
        try:
            last_send = time.time()
            last_status = time.time()
            
            while self.running:
                # Send data at ~10Hz
                if time.time() - last_send > 0.1:
                    self.fuse_and_send()
                    last_send = time.time()
                    
                # Print status at 1Hz
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()
                    
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            
        finally:
            self.running = False
            
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
                    
            print("✓ Proximity bridge stopped")

if __name__ == "__main__":
    bridge = SimpleProximityBridge()
    bridge.run()
