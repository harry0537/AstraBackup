#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge Debug v4
Debug version with extensive logging and diagnostics
"""

import time
import math
import threading
import numpy as np
import os
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

class ComboProximityBridgeDebug:
    def __init__(self):
        # Device configurations
        self.lidar_port = '/dev/ttyUSB0'
        self.pixhawk_port = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
        self.pixhawk_baud = 57600
        
        # Fallback Pixhawk ports
        self.pixhawk_fallback_ports = [
            '/dev/ttyACM0',
            '/dev/ttyACM1'
        ]
        
        # Sensor instances
        self.lidar = None
        self.realsense_pipeline = None
        self.mavlink_connection = None
        
        # Data storage
        self.proximity_data = [0] * 8
        self.data_lock = threading.Lock()
        
        # Debug tracking
        self.debug_stats = {
            'lidar_scans': 0,
            'lidar_errors': 0,
            'lidar_timeouts': 0,
            'realsense_frames': 0,
            'realsense_errors': 0,
            'mavlink_sends': 0,
            'mavlink_errors': 0,
            'start_time': time.time()
        }
        
        # System state
        self.running = True
        self.debug_level = 2  # 0=minimal, 1=normal, 2=verbose
        
        print("Project Astra NZ - Combo Proximity Bridge DEBUG v4")
        print("=" * 60)
        print("DEBUG MODE: Extensive logging enabled")
        print("=" * 60)

    def debug_print(self, level, message):
        """Print debug message based on level"""
        if level <= self.debug_level:
            timestamp = time.strftime('%H:%M:%S')
            print(f"[{timestamp}] {message}")

    def check_device_permissions(self):
        """Check device file permissions"""
        print("\nChecking device permissions...")
        
        devices = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyACM1']
        for device in devices:
            if os.path.exists(device):
                stat_info = os.stat(device)
                perms = oct(stat_info.st_mode)[-3:]
                readable = os.access(device, os.R_OK)
                writable = os.access(device, os.W_OK)
                print(f"  {device}: perms={perms}, R={readable}, W={writable}")
            else:
                print(f"  {device}: NOT FOUND")

    def initialize_sensors(self):
        """Initialize all sensors with detailed logging"""
        print("\nInitializing sensors with debug logging...")
        
        # Check permissions first
        self.check_device_permissions()
        
        # Initialize RPLidar
        if RPLIDAR_AVAILABLE:
            print(f"\nInitializing RPLidar at {self.lidar_port}...")
            try:
                self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=3)
                
                # Get device info
                info = self.lidar.get_info()
                health = self.lidar.get_health()
                
                print(f"  Model: {info['model']}")
                print(f"  Firmware: {info['fw']}")
                print(f"  Hardware: {info['hw']}")
                print(f"  Serial: {info['sn']}")
                print(f"  Health: {health[0]} ({health[1]})")
                print("  ✓ RPLidar S3 connected successfully")
                
            except Exception as e:
                print(f"  ✗ RPLidar initialization failed: {e}")
                self.lidar = None
        else:
            print("  RPLidar library not available")
        
        # Initialize RealSense
        if REALSENSE_AVAILABLE:
            print("\nInitializing RealSense D435i...")
            try:
                # List available devices
                ctx = rs.context()
                devices = ctx.query_devices()
                print(f"  Found {len(devices)} RealSense device(s)")
                
                if len(devices) > 0:
                    device = devices[0]
                    print(f"  Device: {device.get_info(rs.camera_info.name)}")
                    print(f"  Serial: {device.get_info(rs.camera_info.serial_number)}")
                    print(f"  Firmware: {device.get_info(rs.camera_info.firmware_version)}")
                
                # Configure pipeline
                self.realsense_pipeline = rs.pipeline()
                config = rs.config()
                config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                
                # Start streaming
                pipeline_profile = self.realsense_pipeline.start(config)
                
                # Test frame capture
                for i in range(3):
                    frames = self.realsense_pipeline.wait_for_frames(timeout_ms=2000)
                    if frames.get_color_frame() and frames.get_depth_frame():
                        print(f"  Test frame {i+1}: OK")
                    else:
                        print(f"  Test frame {i+1}: FAILED")
                
                print("  ✓ RealSense D435i connected and streaming")
                
            except Exception as e:
                print(f"  ✗ RealSense initialization failed: {e}")
                if self.realsense_pipeline:
                    try:
                        self.realsense_pipeline.stop()
                    except:
                        pass
                self.realsense_pipeline = None
        else:
            print("  RealSense library not available")
        
        # Initialize MAVLink
        if MAVLINK_AVAILABLE:
            print("\nInitializing MAVLink connection...")
            ports_to_try = [self.pixhawk_port] + self.pixhawk_fallback_ports
            
            for port in ports_to_try:
                print(f"  Trying {port}...")
                try:
                    if not os.path.exists(port):
                        print(f"    Device file not found")
                        continue
                    
                    self.mavlink_connection = mavutil.mavlink_connection(
                        port, baud=self.pixhawk_baud
                    )
                    
                    print(f"    Waiting for heartbeat...")
                    self.mavlink_connection.wait_heartbeat(timeout=10)
                    
                    # Get system info
                    msg = self.mavlink_connection.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
                    if msg:
                        print(f"    System ID: {msg.get_srcSystem()}")
                        print(f"    Component ID: {msg.get_srcComponent()}")
                        print(f"    Vehicle Type: {msg.type}")
                        print(f"    Autopilot: {msg.autopilot}")
                        print(f"  ✓ Pixhawk connected at {port}")
                        break
                    
                except Exception as e:
                    print(f"    Connection failed: {e}")
                    continue
            
            if not self.mavlink_connection:
                print("  ✗ Could not connect to Pixhawk on any port")
        else:
            print("  MAVLink library not available")

    def collect_lidar_data(self):
        """Debug version of LiDAR data collection"""
        if not self.lidar:
            return
        
        self.debug_print(1, "Starting LiDAR data collection thread...")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            scan_start = time.time()
            
            try:
                # Clear and restart
                self.debug_print(2, "Stopping and clearing LiDAR buffer...")
                self.lidar.stop()
                time.sleep(0.1)
                self.lidar.clear_input()
                self.lidar.start_scan()
                
                # Collect scan data
                sector_distances = defaultdict(list)
                measurement_count = 0
                scan_timeout = 2.0
                
                self.debug_print(2, "Starting LiDAR scan collection...")
                
                for measurement in self.lidar.iter_scans(scan_type='express'):
                    if time.time() - scan_start > scan_timeout:
                        self.debug_stats['lidar_timeouts'] += 1
                        self.debug_print(1, f"LiDAR scan timeout after {scan_timeout}s")
                        break
                    
                    if not self.running:
                        break
                    
                    # Process measurements
                    for angle, distance, quality in measurement:
                        measurement_count += 1
                        if distance > 0 and quality > 10:
                            distance_m = distance / 1000.0
                            if 0.2 <= distance_m <= 25.0:
                                sector = self.angle_to_sector(angle)
                                sector_distances[sector].append(distance_m)
                    
                    # Stop after collecting enough data
                    if len(sector_distances) >= 6:
                        break
                
                scan_duration = time.time() - scan_start
                
                # Process and store data
                if sector_distances:
                    with self.data_lock:
                        for sector in range(8):
                            if sector in sector_distances:
                                old_value = self.proximity_data[sector]
                                new_value = min(sector_distances[sector])
                                self.proximity_data[sector] = new_value
                                
                                if abs(old_value - new_value) > 0.5:  # Significant change
                                    self.debug_print(2, f"Sector {sector}: {old_value:.2f}m → {new_value:.2f}m")
                    
                    self.debug_stats['lidar_scans'] += 1
                    consecutive_errors = 0
                    
                    self.debug_print(2, f"LiDAR scan complete: {measurement_count} measurements, "
                                      f"{len(sector_distances)} sectors, {scan_duration:.2f}s")
                else:
                    self.debug_print(1, "LiDAR scan produced no valid data")
                
                time.sleep(0.05)
                
            except Exception as e:
                consecutive_errors += 1
                self.debug_stats['lidar_errors'] += 1
                self.debug_print(1, f"LiDAR error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.debug_print(0, "Too many LiDAR errors, attempting restart...")
                    try:
                        self.lidar.disconnect()
                        time.sleep(2)
                        self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=3)
                        consecutive_errors = 0
                        self.debug_print(1, "LiDAR restart successful")
                    except Exception as restart_error:
                        self.debug_print(0, f"LiDAR restart failed: {restart_error}")
                        time.sleep(5)
                
                time.sleep(1)

    def collect_realsense_data(self):
        """Debug version of RealSense data collection"""
        if not self.realsense_pipeline:
            return
        
        self.debug_print(1, "Starting RealSense data collection thread...")
        
        while self.running:
            frame_start = time.time()
            
            try:
                # Get frames
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=1000)
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()
                
                if depth_frame:
                    # Convert to numpy array
                    depth_array = np.asanyarray(depth_frame.get_data())
                    height, width = depth_array.shape
                    
                    # Sample center region
                    center_x, center_y = width // 2, height // 2
                    sample_size = 50
                    
                    x1 = max(0, center_x - sample_size)
                    x2 = min(width, center_x + sample_size)
                    y1 = max(0, center_y - sample_size)
                    y2 = min(height, center_y + sample_size)
                    
                    center_region = depth_array[y1:y2, x1:x2]
                    valid_depths = center_region[(center_region > 200) & (center_region < 25000)]
                    
                    if len(valid_depths) > 100:
                        min_distance = float(np.min(valid_depths)) / 1000.0
                        avg_distance = float(np.mean(valid_depths)) / 1000.0
                        
                        # Update forward sector
                        with self.data_lock:
                            old_value = self.proximity_data[0]
                            if self.proximity_data[0] == 0 or min_distance < self.proximity_data[0]:
                                self.proximity_data[0] = min_distance
                                if abs(old_value - min_distance) > 0.5:
                                    self.debug_print(2, f"RealSense forward: {old_value:.2f}m → {min_distance:.2f}m")
                        
                        self.debug_print(2, f"RealSense: {len(valid_depths)} valid pixels, "
                                          f"min={min_distance:.2f}m, avg={avg_distance:.2f}m")
                    else:
                        self.debug_print(2, f"RealSense: insufficient valid depth data ({len(valid_depths)} pixels)")
                    
                    self.debug_stats['realsense_frames'] += 1
                    
                    frame_duration = time.time() - frame_start
                    self.debug_print(2, f"RealSense frame processed in {frame_duration:.3f}s")
                
                time.sleep(0.1)
                
            except Exception as e:
                self.debug_stats['realsense_errors'] += 1
                self.debug_print(1, f"RealSense error: {e}")
                time.sleep(1)

    def send_proximity_data(self):
        """Debug version of MAVLink data transmission"""
        if not self.mavlink_connection:
            return
        
        self.debug_print(1, "Starting MAVLink transmission thread...")
        
        while self.running:
            send_start = time.time()
            
            try:
                with self.data_lock:
                    distances = []
                    for sector in range(8):
                        distance_cm = int(self.proximity_data[sector] * 100)
                        distance_cm = max(20, min(2500, distance_cm))
                        distances.append(distance_cm)
                
                current_time_ms = int(time.time() * 1000)
                
                # Send distance sensor messages
                for sector in range(8):
                    self.mavlink_connection.mav.distance_sensor_send(
                        current_time_ms,
                        distances[sector],
                        distances[sector],
                        distances[sector],
                        0,
                        sector,
                        sector * 45,
                        255,
                        0,
                        0,
                        [0,0,0,0],
                        195
                    )
                
                self.debug_stats['mavlink_sends'] += 1
                send_duration = time.time() - send_start
                
                self.debug_print(2, f"MAVLink: sent 8 sectors in {send_duration:.3f}s")
                self.debug_print(2, f"Distances: {[f'{d}cm' for d in distances]}")
                
                time.sleep(0.5)
                
            except Exception as e:
                self.debug_stats['mavlink_errors'] += 1
                self.debug_print(1, f"MAVLink error: {e}")
                time.sleep(1)

    def angle_to_sector(self, angle_deg):
        """Convert angle to sector with debug info"""
        angle_deg = angle_deg % 360
        sector = int((angle_deg + 22.5) / 45) % 8
        return sector

    def print_debug_status(self):
        """Print detailed debug status"""
        while self.running:
            try:
                uptime = time.time() - self.debug_stats['start_time']
                
                print(f"\n{'='*80}")
                print(f"DEBUG STATUS - {time.strftime('%H:%M:%S')} (Uptime: {uptime:.1f}s)")
                print(f"{'='*80}")
                
                # Performance stats
                print(f"LiDAR Scans:   {self.debug_stats['lidar_scans']:6} "
                      f"(Errors: {self.debug_stats['lidar_errors']}, "
                      f"Timeouts: {self.debug_stats['lidar_timeouts']})")
                
                print(f"RealSense:     {self.debug_stats['realsense_frames']:6} "
                      f"(Errors: {self.debug_stats['realsense_errors']})")
                
                print(f"MAVLink Sends: {self.debug_stats['mavlink_sends']:6} "
                      f"(Errors: {self.debug_stats['mavlink_errors']})")
                
                # Current proximity data
                with self.data_lock:
                    print(f"\nProximity Data (meters):")
                    directions = ["N ", "NE", "E ", "SE", "S ", "SW", "W ", "NW"]
                    
                    for i in range(4):
                        line1 = f"  {directions[i]:2}: {self.proximity_data[i]:6.2f}m"
                        line2 = f"  {directions[i+4]:2}: {self.proximity_data[i+4]:6.2f}m"
                        print(f"{line1} | {line2}")
                
                # Success rates
                if self.debug_stats['lidar_scans'] > 0:
                    lidar_success = (self.debug_stats['lidar_scans'] / 
                                   max(1, self.debug_stats['lidar_scans'] + self.debug_stats['lidar_errors'])) * 100
                    print(f"\nLiDAR Success Rate: {lidar_success:.1f}%")
                
                if self.debug_stats['realsense_frames'] > 0:
                    rs_success = (self.debug_stats['realsense_frames'] / 
                                 max(1, self.debug_stats['realsense_frames'] + self.debug_stats['realsense_errors'])) * 100
                    print(f"RealSense Success Rate: {rs_success:.1f}%")
                
                time.sleep(5)  # More frequent updates in debug mode
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Debug status error: {e}")
                time.sleep(5)

    def run(self):
        """Main execution with debug mode"""
        try:
            # Initialize
            self.initialize_sensors()
            
            # Check sensors
            if not self.lidar and not self.realsense_pipeline:
                print("ERROR: No sensors available")
                return
            
            if not self.mavlink_connection:
                print("ERROR: No MAVLink connection")
                return
            
            print("\nStarting debug proximity bridge...")
            print("Debug Level: 2 (Verbose)")
            print("Press Ctrl+C to stop\n")
            
            # Start threads
            threads = []
            
            if self.lidar:
                t1 = threading.Thread(target=self.collect_lidar_data, daemon=True)
                t1.start()
                threads.append(t1)
            
            if self.realsense_pipeline:
                t2 = threading.Thread(target=self.collect_realsense_data, daemon=True)
                t2.start()
                threads.append(t2)
            
            t3 = threading.Thread(target=self.send_proximity_data, daemon=True)
            t3.start()
            threads.append(t3)
            
            # Run debug status
            self.print_debug_status()
            
        except KeyboardInterrupt:
            print("\n\nShutdown requested...")
            self.shutdown()
        except Exception as e:
            print(f"System error: {e}")
            self.shutdown()

    def shutdown(self):
        """Clean shutdown"""
        print("Shutting down debug proximity bridge...")
        self.running = False
        
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
        
        print("Debug shutdown complete")

if __name__ == "__main__":
    bridge = ComboProximityBridgeDebug()
    bridge.run()
