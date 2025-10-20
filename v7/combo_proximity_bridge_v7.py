#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V7
Accepts rplidar library buffer limitations, focuses on RealSense reliability
Component 195 - Production Ready - Clean Version
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

# Hardware configuration
LIDAR_PORT = '/dev/ttyUSB1'
PIXHAWK_PORT = '/dev/ttyACM0'
PIXHAWK_BAUD = 57600
COMPONENT_ID = 195

class ComboProximityBridge:
    def __init__(self):
        self.lidar = None
        self.mavlink = None
        self.pipeline = None
        self.running = True
        
        # Proximity configuration
        self.min_distance_cm = 20
        self.max_distance_cm = 2500
        self.quality_threshold = 10
        self.num_sectors = 8

        # Sensor data storage with thread safety
        self.lidar_sectors = [self.max_distance_cm] * self.num_sectors
        self.realsense_sectors = [self.max_distance_cm] * self.num_sectors
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'lidar_attempts': 0,
            'lidar_success': 0,
            'realsense_success': 0,
            'messages_sent': 0,
            'start_time': time.time()
        }
        
        # Suppress rplidar buffer warnings
        self.suppress_warnings = True

    def connect_lidar(self):
        """Connect to RPLidar S3 - BEST EFFORT"""
        try:
            print(f"Connecting RPLidar at {LIDAR_PORT}")
            self.lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=1)
            
            info = self.lidar.get_info()
            health = self.lidar.get_health()
            print(f"✓ RPLidar S3: Model {info['model']}, Health {health[0]}")
            print("  ⚠ Note: Buffer warnings are from rplidar library (known issue)")
            return True
            
        except Exception as e:
            print(f"✗ RPLidar failed: {e}")
            return False
            
    def connect_realsense(self):
        """Connect to Intel RealSense D435i - PRIMARY SENSOR"""
        try:
            if not REALSENSE_AVAILABLE:
                return False
            print("Connecting RealSense D435i (PRIMARY forward sensor)")
            self.pipeline = rs.pipeline()
            config = rs.config()
            # Higher framerate for better responsiveness
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 30)
            self.pipeline.start(config)
            
            for _ in range(10):
                self.pipeline.wait_for_frames()
            print("✓ RealSense D435i connected - PRIMARY SENSOR")
            return True
        except Exception as e:
            print(f"✗ RealSense failed: {e}")
            self.pipeline = None
            return False
            
    def connect_pixhawk(self):
        """Connect to Pixhawk via MAVLink"""
        try:
            candidates = [PIXHAWK_PORT] + [f'/dev/ttyACM{i}' for i in range(4)]
            
            for port in candidates:
                if not os.path.exists(port):
                    continue
                try:
                    print(f"Connecting Pixhawk at {port}")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=255,
                        source_component=COMPONENT_ID
                    )
                    self.mavlink.wait_heartbeat(timeout=5)
                    print("✓ Pixhawk connected")
                    return True
                except:
                    self.mavlink = None
            
            raise RuntimeError('No Pixhawk port available')
            
        except Exception as e:
            print(f"✗ Pixhawk failed: {e}")
            return False
            
    def lidar_thread(self):
        """LiDAR thread - BEST EFFORT with graceful failure"""
        
        # Redirect stderr to suppress library warnings if requested
        if self.suppress_warnings:
            sys.stderr = open(os.devnull, 'w')
        
        while self.running:
            if not self.lidar:
                time.sleep(1)
                continue

            self.stats['lidar_attempts'] += 1
            
            try:
                # Simple approach: quick scan, quick exit
                self.lidar.start_motor()
                time.sleep(0.5)
                
                # Try to get one scan worth of data
                scan_data = []
                start = time.time()
                
                try:
                    # Use iter_scans with timeout
                    for scan in self.lidar.iter_scans(max_buf_meas=500):
                        for point in scan:
                            if len(point) >= 3:
                                quality = point[0] if len(point) == 3 else point[1]
                                angle = point[1] if len(point) == 3 else point[2]
                                distance = point[2] if len(point) == 3 else point[3]
                                
                                if quality > self.quality_threshold and distance > 0:
                                    scan_data.append((angle, distance))
                        
                        if len(scan_data) > 20 or time.time() - start > 1:
                            break
                except:
                    pass
                
                self.lidar.stop()
                self.lidar.stop_motor()
                
                # Process if we got anything
                if len(scan_data) > 5:
                    sectors = [self.max_distance_cm] * self.num_sectors
                    for angle, distance_mm in scan_data:
                        distance_cm = max(self.min_distance_cm, 
                                        min(int(distance_mm / 10), self.max_distance_cm))
                        sector = int((angle + 22.5) / 45) % 8
                        if distance_cm < sectors[sector]:
                            sectors[sector] = distance_cm
                    
                    with self.lock:
                        self.lidar_sectors = sectors
                    self.stats['lidar_success'] += 1
                
                time.sleep(0.5)
                
            except Exception:
                try:
                    self.lidar.stop()
                    self.lidar.stop_motor()
                except:
                    pass
                time.sleep(1)
                    
    def realsense_thread(self):
        """RealSense - PRIMARY sensor for forward detection"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue

            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=500)
                depth_frame = frames.get_depth_frame()
                if not depth_frame:
                    time.sleep(0.03)
                    continue

                width = depth_frame.get_width()
                height = depth_frame.get_height()
                sectors = [self.max_distance_cm] * self.num_sectors

                # Forward 3 sectors with detailed sampling
                regions = [
                    (height//3, 2*height//3, width//3, 2*width//3),   # Center
                    (height//3, 2*height//3, 2*width//3, width),      # Right
                    (height//3, 2*height//3, 0, width//3),            # Left
                ]
                forward_sectors = [0, 1, 7]

                for i, (y1, y2, x1, x2) in enumerate(regions):
                    step = 10
                    depths = []
                    for y in range(y1, y2 - (y2 - y1)//3, step):
                        for x in range(x1, x2, step):
                            d = depth_frame.get_distance(x, y)
                            if 0.2 < d < 25.0:
                                depths.append(d)
                    
                    if len(depths) > 30:
                        closest_m = float(np.percentile(depths, 5))
                        closest_cm = max(self.min_distance_cm, 
                                       min(int(closest_m * 100), self.max_distance_cm))
                        sectors[forward_sectors[i]] = closest_cm

                with self.lock:
                    self.realsense_sectors = sectors
                self.stats['realsense_success'] += 1

                time.sleep(0.03)  # ~30Hz

            except:
                time.sleep(0.05)
                
    def fuse_and_send(self):
        """Fuse sensor data - RealSense priority for forward"""
        if not self.mavlink:
            return

        with self.lock:
            lidar = self.lidar_sectors.copy()
            rsc = self.realsense_sectors.copy()

        # PRIORITY: RealSense for forward (most critical)
        fused = [self.max_distance_cm] * self.num_sectors
        for i in range(self.num_sectors):
            if i in [0, 1, 7]:  # Forward arc - RealSense is reliable
                fused[i] = min(rsc[i], lidar[i])
            else:  # Sides/rear - LiDAR when available
                if lidar[i] < self.max_distance_cm:
                    fused[i] = lidar[i]
                elif rsc[i] < self.max_distance_cm:
                    fused[i] = rsc[i]

        # Send to Pixhawk
        orientations = [0, 1, 2, 3, 4, 5, 6, 7]
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        for sector_id, distance_cm in enumerate(fused):
            try:
                self.mavlink.mav.distance_sensor_send(
                    time_boot_ms=timestamp,
                    min_distance=self.min_distance_cm,
                    max_distance=self.max_distance_cm,
                    current_distance=int(distance_cm),
                    type=0,
                    id=sector_id,
                    orientation=orientations[sector_id],
                    covariance=0
                )
            except:
                pass

        self.stats['messages_sent'] += self.num_sectors

        # Publish status
        try:
            payload = {
                'timestamp': time.time(),
                'sectors_cm': fused,
                'min_cm': int(min(fused)),
                'lidar_cm': lidar,
                'realsense_cm': rsc,
                'messages_sent': self.stats['messages_sent']
            }
            with open('/tmp/proximity_v7.json.tmp', 'w') as f:
                json.dump(payload, f)
            os.replace('/tmp/proximity_v7.json.tmp', '/tmp/proximity_v7.json')
        except:
            pass
        
    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        l_rate = int((self.stats['lidar_success'] / max(1, self.stats['lidar_attempts'])) * 100)
        
        with self.lock:
            lidar_min = min(self.lidar_sectors)
            rs_min = min(self.realsense_sectors)
        
        # Clean status without buffer warnings
        print(f"\r[{uptime:3d}s] "
              f"Forward(RS):{rs_min/100:.1f}m ✓ | "
              f"Lidar:{l_rate:2d}% {lidar_min/100:.1f}m | "
              f"TX:{self.stats['messages_sent']:5d}", end='', flush=True)
              
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V7 - Production")
        print("=" * 60)
        
        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense() if REALSENSE_AVAILABLE else False
        
        if not pixhawk_ok:
            print("✗ Cannot continue without Pixhawk")
            return
            
        if not realsense_ok:
            print("✗ RealSense required for forward detection")
            return
            
        if lidar_ok:
            t = threading.Thread(target=self.lidar_thread, daemon=True)
            t.start()
            
        if realsense_ok:
            t = threading.Thread(target=self.realsense_thread, daemon=True)
            t.start()
            
        print("\n✓ Proximity bridge operational - PRODUCTION MODE")
        print("  • PRIMARY: RealSense (forward 135° arc)")
        print("  • SECONDARY: LiDAR (side/rear, best effort)")
        print("  • Update: 10Hz to Mission Planner")
        print("  • Note: Buffer warnings suppressed\n")
        
        try:
            last_send = time.time()
            last_status = time.time()
            
            while self.running:
                if time.time() - last_send > 0.1:
                    self.fuse_and_send()
                    last_send = time.time()
                    
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()
                    
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\nShutdown initiated...")
            
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
            
            # Restore stderr
            if self.suppress_warnings:
                sys.stderr = sys.__stderr__
                    
            print("✓ Proximity bridge stopped")

if __name__ == "__main__":
    bridge = ComboProximityBridge()
    bridge.run()
