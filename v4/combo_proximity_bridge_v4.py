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
import json
import os

# RealSense is optional; guard import for headless/absent setups
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except Exception:
    REALSENSE_AVAILABLE = False

# CRITICAL: Default device paths (udev symlinks preferred on Ubuntu)
LIDAR_PORT = '/dev/rplidar'  # udev symlink fallback to /dev/ttyUSB0
PIXHAWK_PORT = '/dev/pixhawk'  # udev symlink fallback to /dev/ttyACM*
PIXHAWK_BAUD = 57600
COMPONENT_ID = 195

class ComboProximityBridge:
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

        # Sensor data storage (centimeters)
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

    def aggressive_buffer_clear(self):
        """Aggressively clear RPLidar serial buffers to avoid backlog."""
        try:
            if self.lidar and hasattr(self.lidar, '_serial') and self.lidar._serial:
                serial_conn = self.lidar._serial
                for _ in range(3):
                    try:
                        serial_conn.reset_input_buffer()
                        serial_conn.reset_output_buffer()
                    except Exception:
                        pass
                    time.sleep(0.05)
                # Drain any remaining data
                try:
                    while getattr(serial_conn, 'in_waiting', 0) > 0:
                        try:
                            serial_conn.read(serial_conn.in_waiting)
                        except Exception:
                            break
                        time.sleep(0.01)
                except Exception:
                    pass
        except Exception:
            pass
        
    def connect_lidar(self):
        """Connect to RPLidar S3"""
        try:
            # Try preferred udev symlink, then common defaults
            candidate_ports = [LIDAR_PORT, '/dev/ttyUSB0', '/dev/ttyUSB1']
            last_error = None
            for port in candidate_ports:
                try:
                    print(f"Connecting to RPLidar at {port}")
                    self.lidar = RPLidar(port, baudrate=1000000, timeout=2)
                    break
                except Exception as e:
                    last_error = e
                    self.lidar = None
            if not self.lidar:
                raise last_error or RuntimeError('No LiDAR port available')
            
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
        """Connect to Intel RealSense D435i with low-res depth for stability"""
        try:
            if not REALSENSE_AVAILABLE:
                return False
            print("Connecting to RealSense D435i")
            self.pipeline = rs.pipeline()
            config = rs.config()
            # Lower resolution and frame rate to reduce CPU and improve stability
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 15)
            self.pipeline.start(config)
            # Warm-up frames
            for _ in range(5):
                self.pipeline.wait_for_frames()
            print("✓ RealSense connected and streaming")
            return True
        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            self.pipeline = None
            return False
            
    def connect_pixhawk(self):
        """Connect to Pixhawk via MAVLink"""
        try:
            # Try preferred udev symlink, then by-id, then ttyACM*
            candidate_ports = [PIXHAWK_PORT,
                               '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00']
            candidate_ports += [f'/dev/ttyACM{i}' for i in range(4)]
            last_error = None
            for port in candidate_ports:
                try:
                    print(f"Connecting to Pixhawk at {port}")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=255,
                        source_component=COMPONENT_ID
                    )
                    self.mavlink.wait_heartbeat(timeout=5)
                    print("✓ Connected to Pixhawk")
                    break
                except Exception as e:
                    last_error = e
                    self.mavlink = None
            if not self.mavlink:
                raise last_error or RuntimeError('No Pixhawk port available')
            
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
        """Background thread using iter_measurments with aggressive buffer control."""
        error_count = 0
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

                # Start motor briefly for a fast sample
                try:
                    self.lidar.start_motor()
                except Exception:
                    pass
                time.sleep(0.2)

                scan_data = []
                measurement_count = 0
                start_time = time.time()

                for measurement in self.lidar.iter_measurments():
                    if not self.running:
                        break
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                        if quality >= self.quality_threshold and distance > 0:
                            scan_data.append((quality, angle, distance))

                    measurement_count += 1
                    # Keep loops short to avoid buffer buildup
                    if len(scan_data) > 20 and time.time() - start_time > 0.5:
                        break
                    if measurement_count > 200 or time.time() - start_time > 1.0:
                        break

                if len(scan_data) > 10:
                    sectors = [self.max_distance_cm] * self.num_sectors
                    for _, angle, distance_mm in [(q, a, d) for (q, a, d) in scan_data]:
                        distance_cm = max(self.min_distance_cm, min(int(distance_mm / 10), self.max_distance_cm))
                        sector = int((angle + 22.5) / 45) % 8
                        if distance_cm < sectors[sector]:
                            sectors[sector] = distance_cm
                    with self.lock:
                        self.lidar_sectors = sectors
                    self.stats['lidar_success'] += 1

                # Stop motor between bursts
                try:
                    self.lidar.stop()
                except Exception:
                    pass
                time.sleep(0.2)

            except Exception:
                error_count += 1
                self.stats['lidar_errors'] += 1
                self.aggressive_buffer_clear()
                if error_count > 5:
                    try:
                        self.lidar.stop()
                        self.lidar.stop_motor()
                        self.lidar.disconnect()
                    except Exception:
                        pass
                    time.sleep(1.0)
                    self.connect_lidar()
                    error_count = 0
                    
    def realsense_thread(self):
        """Thread for RealSense depth processing focusing on forward sectors."""
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

                # Forward ROI regions (center, right, left)
                regions = [
                    (height//3, 2*height//3, width//3, 2*width//3),  # center -> sector 0
                    (height//3, 2*height//3, 2*width//3, width),      # right  -> sector 1
                    (height//3, 2*height//3, 0, width//3),            # left   -> sector 7
                ]
                forward_sectors = [0, 1, 7]

                for i, (y1, y2, x1, x2) in enumerate(regions):
                    # Sample the closer two-thirds vertically in the ROI
                    step_x = max(1, (x2 - x1) // 30)
                    step_y = max(1, (y2 - y1) // 20)
                    depths = []
                    for y in range(y1, y2 - (y2 - y1)//3, step_y):
                        for x in range(x1, x2, step_x):
                            d = depth_frame.get_distance(x, y)  # meters
                            if 0.2 < d < 25.0:
                                depths.append(d)
                    if len(depths) > 30:
                        # Use 5th percentile for robustness to outliers
                        closest_m = float(np.percentile(depths, 5))
                        closest_cm = max(self.min_distance_cm, min(int(closest_m * 100), self.max_distance_cm))
                        sectors[forward_sectors[i]] = closest_cm

                with self.lock:
                    self.realsense_sectors = sectors
                self.stats['realsense_success'] += 1

            except Exception:
                # Silent fail for RealSense
                time.sleep(0.05)
                
    def fuse_and_send(self):
        """Fuse LiDAR/RealSense sector data and send MAVLink messages."""
        if not self.mavlink:
            return

        with self.lock:
            lidar = self.lidar_sectors.copy()
            rsc = self.realsense_sectors.copy()

        # Fuse: forward sectors (0,1,7) prefer RealSense, else LiDAR
        fused = [self.max_distance_cm] * self.num_sectors
        for i in range(self.num_sectors):
            if i in [0, 1, 7]:
                fused[i] = min(rsc[i], lidar[i])
            else:
                fused[i] = min(lidar[i], rsc[i])

        # Mission Planner-friendly orientation mapping for 8 sectors
        orientations = [0, 2, 2, 4, 4, 6, 6, 0]
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        for sector_id, distance_cm in enumerate(fused):
            try:
                self.mavlink.mav.distance_sensor_send(
                    time_boot_ms=timestamp,
                    min_distance=self.min_distance_cm,
                    max_distance=self.max_distance_cm,
                    current_distance=int(distance_cm),
                    type=1,  # generic/ultrasound; works for proximity display
                    id=sector_id,
                    orientation=orientations[sector_id],
                    covariance=0
                )
            except Exception:
                pass

        self.stats['messages_sent'] += self.num_sectors

        # Also publish proximity locally for relay to pick up
        try:
            payload = {
                'timestamp': time.time(),
                'sectors_cm': fused,
                'min_cm': int(min(fused)),
            }
            tmp_path = '/tmp/proximity_v4.json.tmp'
            out_path = '/tmp/proximity_v4.json'
            with open(tmp_path, 'w') as f:
                json.dump(payload, f)
            os.replace(tmp_path, out_path)
        except Exception:
            pass
        
    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        with self.lock:
            lidar_min_cm = min(self.lidar_sectors) if self.lidar_sectors else self.max_distance_cm
            rs_min_cm = min(self.realsense_sectors) if self.realsense_sectors else self.max_distance_cm
        print(
            f"\r[{uptime:4d}s] LiDAR: {self.stats['lidar_success']:4d} OK, "
            f"{self.stats['lidar_errors']:3d} ERR | "
            f"RealSense: {self.stats['realsense_success']:4d} OK | "
            f"Sent: {self.stats['messages_sent']:5d} | "
            f"Min: L={lidar_min_cm/100:.1f}m R={rs_min_cm/100:.1f}m",
            end='' 
        )
              
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V4 - Component 195")
        print("=" * 60)
        
        # Connect all systems
        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()
        realsense_ok = self.connect_realsense() if REALSENSE_AVAILABLE else False
        
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