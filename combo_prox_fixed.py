#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V6
Based on proven working version with aggressive buffer management
Component 195 - Proximity sensing for ArduPilot
"""

import time
import threading
import numpy as np
import json
import os
from rplidar import RPLidar
from pymavlink import mavutil

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

# Hardware configuration - CRITICAL: Do not change without testing
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
            'lidar_success': 0,
            'lidar_errors': 0,
            'realsense_success': 0,
            'messages_sent': 0,
            'start_time': time.time()
        }

    def _yield_lidar_measurements(self):
        """Handle different rplidar library versions"""
        if hasattr(self.lidar, 'iter_measurments'):
            for m in self.lidar.iter_measurments():
                yield m
        elif hasattr(self.lidar, 'iter_measurements'):
            for m in self.lidar.iter_measurements():
                yield m
        elif hasattr(self.lidar, 'iter_scans'):
            for scan in self.lidar.iter_scans():
                for item in scan:
                    if isinstance(item, (list, tuple)) and len(item) == 3:
                        q, a, d = item
                        yield (0, q, a, d)
                    else:
                        yield item
        else:
            raise AttributeError("No compatible RPLidar iterator found")

    def aggressive_buffer_clear(self):
        """Clear RPLidar serial buffers - CRITICAL for reliability"""
        try:
            if self.lidar and hasattr(self.lidar, '_serial') and self.lidar._serial:
                serial_conn = self.lidar._serial
                for _ in range(3):
                    try:
                        serial_conn.reset_input_buffer()
                        serial_conn.reset_output_buffer()
                    except:
                        pass
                    time.sleep(0.05)
                # Drain remaining data
                try:
                    while getattr(serial_conn, 'in_waiting', 0) > 0:
                        serial_conn.read(serial_conn.in_waiting)
                        time.sleep(0.01)
                except:
                    pass
        except:
            pass
        
    def connect_lidar(self):
        """Connect to RPLidar S3"""
        try:
            print(f"Connecting RPLidar at {LIDAR_PORT}")
            self.lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=2)
            
            self.aggressive_buffer_clear()
            info = self.lidar.get_info()
            health = self.lidar.get_health()
            print(f"✓ RPLidar S3: Model {info['model']}, Health {health[0]}")
            
            self.lidar.start_motor()
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"✗ RPLidar failed: {e}")
            return False
            
    def connect_realsense(self):
        """Connect to Intel RealSense D435i"""
        try:
            if not REALSENSE_AVAILABLE:
                return False
            print("Connecting RealSense D435i")
            self.pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 15)
            self.pipeline.start(config)
            
            # Warm-up
            for _ in range(5):
                self.pipeline.wait_for_frames()
            print("✓ RealSense D435i connected")
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
        """Background thread for RPLidar processing"""
        buffer_clear_interval = 0

        while self.running:
            if not self.lidar:
                time.sleep(0.5)
                continue

            try:
                buffer_clear_interval += 1
                if buffer_clear_interval >= 5:
                    self.aggressive_buffer_clear()
                    buffer_clear_interval = 0

                try:
                    self.lidar.start_motor()
                except:
                    pass
                time.sleep(0.2)

                scan_data = []
                measurement_count = 0
                start_time = time.time()

                for measurement in self._yield_lidar_measurements():
                    if not self.running:
                        break
                    
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                    elif len(measurement) == 3:
                        quality, angle, distance = measurement
                    else:
                        continue

                    if quality >= self.quality_threshold and distance > 0:
                        scan_data.append((quality, angle, distance))

                    measurement_count += 1
                    if len(scan_data) > 20 and time.time() - start_time > 0.5:
                        break
                    if measurement_count > 200 or time.time() - start_time > 1.0:
                        break

                if len(scan_data) > 10:
                    sectors = [self.max_distance_cm] * self.num_sectors
                    for _, angle, distance_mm in scan_data:
                        distance_cm = max(self.min_distance_cm, 
                                        min(int(distance_mm / 10), self.max_distance_cm))
                        sector = int((angle + 22.5) / 45) % 8
                        if distance_cm < sectors[sector]:
                            sectors[sector] = distance_cm
                    
                    with self.lock:
                        self.lidar_sectors = sectors
                    self.stats['lidar_success'] += 1

                try:
                    self.lidar.stop()
                except:
                    pass
                time.sleep(0.2)

            except Exception:
                self.stats['lidar_errors'] += 1
                self.aggressive_buffer_clear()
                time.sleep(0.5)
                    
    def realsense_thread(self):
        """Thread for RealSense depth processing"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue

            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=300)
                depth_frame = frames.get_depth_frame()
                if not depth_frame:
                    time.sleep(0.05)
                    continue

                width = depth_frame.get_width()
                height = depth_frame.get_height()
                sectors = [self.max_distance_cm] * self.num_sectors

                # Forward ROI regions
                regions = [
                    (height//3, 2*height//3, width//3, 2*width//3),
                    (height//3, 2*height//3, 2*width//3, width),
                    (height//3, 2*height//3, 0, width//3),
                ]
                forward_sectors = [0, 1, 7]

                for i, (y1, y2, x1, x2) in enumerate(regions):
                    step_x = max(1, (x2 - x1) // 30)
                    step_y = max(1, (y2 - y1) // 20)
                    depths = []
                    for y in range(y1, y2 - (y2 - y1)//3, step_y):
                        for x in range(x1, x2, step_x):
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

            except:
                time.sleep(0.05)
                
    def fuse_and_send(self):
        """Fuse sensor data and send to Pixhawk"""
        if not self.mavlink:
            return

        with self.lock:
            lidar = self.lidar_sectors.copy()
            rsc = self.realsense_sectors.copy()

        # Fuse: forward sectors prefer RealSense, others prefer LiDAR
        fused = [self.max_distance_cm] * self.num_sectors
        for i in range(self.num_sectors):
            if i in [0, 1, 7]:
                fused[i] = min(rsc[i], lidar[i])
            else:
                fused[i] = min(lidar[i], rsc[i])

        # Send MAVLink messages
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

        # Publish for other components
        try:
            payload = {
                'timestamp': time.time(),
                'sectors_cm': fused,
                'min_cm': int(min(fused)),
                'lidar_cm': lidar,
                'realsense_cm': rsc,
                'messages_sent': self.stats['messages_sent']
            }
            with open('/tmp/proximity_v6.json.tmp', 'w') as f:
                json.dump(payload, f)
            os.replace('/tmp/proximity_v6.json.tmp', '/tmp/proximity_v6.json')
        except:
            pass
        
    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        with self.lock:
            lidar_min = min(self.lidar_sectors)
            rs_min = min(self.realsense_sectors)
        print(f"\r[{uptime:4d}s] L:{self.stats['lidar_success']:4d}✓ "
              f"{self.stats['lidar_errors']:3d}✗ | "
              f"R:{self.stats['realsense_success']:4d}✓ | "
              f"TX:{self.stats['messages_sent']:5d} | "
              f"Min: L={lidar_min/100:.1f}m R={rs_min/100:.1f}m", end='')
              
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V6 - Component 195")
        print("=" * 60)
        
        # Connect all systems
        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense() if REALSENSE_AVAILABLE else False
        
        if not pixhawk_ok:
            print("✗ Cannot continue without Pixhawk")
            return
            
        if not lidar_ok and not realsense_ok:
            print("✗ No sensors available")
            return
            
        # Start sensor threads
        if lidar_ok:
            t = threading.Thread(target=self.lidar_thread, daemon=True)
            t.start()
            
        if realsense_ok:
            t = threading.Thread(target=self.realsense_thread, daemon=True)
            t.start()
            
        print("\n✓ Proximity bridge operational")
        print("  • 8-sector data to Mission Planner")
        print("  • Forward: RealSense priority")
        print("  • Sides/rear: RPLidar data\n")
        
        # Main loop
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
                    
            print("✓ Proximity bridge stopped")

if __name__ == "__main__":
    bridge = ComboProximityBridge()
    bridge.run()
