#!/usr/bin/env python3
"""
Project Astra NZ - Rover Data Relay System v1
Relays real-time sensor and telemetry data to AWS dashboard server
"""

import time
import json
import threading
import requests
import numpy as np
from datetime import datetime
import queue
import cv2
import base64

# Sensor imports
try:
    from rplidar import RPLidar
    RPLIDAR_AVAILABLE = True
except ImportError:
    RPLIDAR_AVAILABLE = False

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False

class RoverDataRelay:
    def __init__(self):
        # AWS Dashboard server configuration
        # UGV-Server-Win2025 (i-03ae6c471d8c10b9c) - Primary rover dashboard
        # AWS internal IP: 172.31.59.82
        # ZeroTier IP: 10.244.77.186 (confirmed via zerotier-cli)
        self.dashboard_ip = "10.244.77.186"  # UGV server ZeroTier IP
        self.dashboard_port = 8080
        self.dashboard_url = f"http://{self.dashboard_ip}:{self.dashboard_port}"
        
        # Data queues for thread communication
        self.lidar_queue = queue.Queue(maxsize=50)
        self.camera_queue = queue.Queue(maxsize=10)
        self.telemetry_queue = queue.Queue(maxsize=100)
        
        # System status tracking
        self.system_status = {
            'rplidar': {'connected': False, 'last_update': 0, 'error_count': 0},
            'realsense': {'connected': False, 'last_update': 0, 'error_count': 0},
            'pixhawk': {'connected': False, 'last_update': 0, 'error_count': 0},
            'dashboard': {'connected': False, 'last_update': 0, 'error_count': 0}
        }
        
        # Initialize sensors
        self.lidar = None
        self.realsense_pipeline = None
        self.mavlink_connection = None
        
        self.running = True
        print(f"Rover Data Relay initialized - Target: {self.dashboard_url}")

    def initialize_sensors(self):
        """Initialize all sensor connections"""
        print("Initializing sensors...")
        
        # Initialize RPLidar
        if RPLIDAR_AVAILABLE:
            try:
                self.lidar = RPLidar('/dev/ttyUSB0', baudrate=1000000, timeout=3)
                self.lidar.connect()
                self.system_status['rplidar']['connected'] = True
                print("✓ RPLidar S3 connected")
            except Exception as e:
                print(f"✗ RPLidar initialization failed: {e}")
        
        # Initialize RealSense
        if REALSENSE_AVAILABLE:
            try:
                self.realsense_pipeline = rs.pipeline()
                config = rs.config()
                config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
                config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                self.realsense_pipeline.start(config)
                
                # Test frame capture
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=2000)
                if frames.get_color_frame() and frames.get_depth_frame():
                    self.system_status['realsense']['connected'] = True
                    print("✓ RealSense D435i connected and streaming")
            except Exception as e:
                print(f"✗ RealSense initialization failed: {e}")
        
        # Initialize MAVLink
        if MAVLINK_AVAILABLE:
            try:
                # Try multiple possible Pixhawk locations
                pixhawk_ports = [
                    '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00',
                    '/dev/ttyACM0',
                    '/dev/ttyACM1'
                ]
                
                for port in pixhawk_ports:
                    try:
                        self.mavlink_connection = mavutil.mavlink_connection(port, baud=57600)
                        self.mavlink_connection.wait_heartbeat(timeout=5)
                        self.system_status['pixhawk']['connected'] = True
                        print(f"✓ Pixhawk connected at {port}")
                        break
                    except:
                        continue
            except Exception as e:
                print(f"✗ MAVLink initialization failed: {e}")

    def collect_lidar_data(self):
        """Collect RPLidar data in separate thread"""
        if not self.lidar:
            return
        
        print("Starting LiDAR data collection...")
        
        while self.running:
            try:
                # Clear old data from lidar buffer
                self.lidar.stop()
                time.sleep(0.1)
                self.lidar.clear_input()
                self.lidar.start_scan()
                
                scan_data = []
                start_time = time.time()
                
                for measurement in self.lidar.iter_scans(scan_type='express'):
                    if not self.running or time.time() - start_time > 1.0:
                        break
                    
                    # Process scan data
                    for angle, distance, quality in measurement:
                        if distance > 0 and quality > 10:
                            scan_data.append({
                                'angle': round(angle, 1),
                                'distance': round(distance/10, 2),  # Convert to cm
                                'quality': quality
                            })
                
                if scan_data:
                    lidar_packet = {
                        'timestamp': time.time(),
                        'sensor': 'rplidar_s3',
                        'scan_count': len(scan_data),
                        'data': scan_data[:360]  # Limit data size
                    }
                    
                    try:
                        self.lidar_queue.put_nowait(lidar_packet)
                        self.system_status['rplidar']['last_update'] = time.time()
                    except queue.Full:
                        self.lidar_queue.get()  # Remove oldest
                        self.lidar_queue.put_nowait(lidar_packet)
                
            except Exception as e:
                self.system_status['rplidar']['error_count'] += 1
                print(f"LiDAR error: {e}")
                time.sleep(1)

    def collect_camera_data(self):
        """Collect RealSense camera data"""
        if not self.realsense_pipeline:
            return
        
        print("Starting camera data collection...")
        
        while self.running:
            try:
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=1000)
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                
                if color_frame and depth_frame:
                    # Convert frames to numpy arrays
                    color_image = np.asanyarray(color_frame.get_data())
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Resize for efficient transmission
                    color_small = cv2.resize(color_image, (320, 240))
                    
                    # Encode image to base64
                    _, buffer = cv2.imencode('.jpg', color_small, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Calculate basic obstacle data from depth
                    depth_array = np.asanyarray(depth_frame.get_data())
                    obstacles = self.detect_obstacles_from_depth(depth_array)
                    
                    camera_packet = {
                        'timestamp': time.time(),
                        'sensor': 'realsense_d435i',
                        'image': img_base64,
                        'obstacles': obstacles,
                        'resolution': '320x240'
                    }
                    
                    try:
                        self.camera_queue.put_nowait(camera_packet)
                        self.system_status['realsense']['last_update'] = time.time()
                    except queue.Full:
                        self.camera_queue.get()  # Remove oldest
                        self.camera_queue.put_nowait(camera_packet)
                
                time.sleep(0.1)  # 10Hz update rate
                
            except Exception as e:
                self.system_status['realsense']['error_count'] += 1
                print(f"Camera error: {e}")
                time.sleep(1)

    def detect_obstacles_from_depth(self, depth_array):
        """Extract obstacle information from depth data"""
        try:
            # Get center region for forward obstacle detection
            h, w = depth_array.shape
            center_region = depth_array[h//3:2*h//3, w//3:2*w//3]
            
            # Filter valid depth values (0.2m to 10m)
            valid_depths = center_region[(center_region > 200) & (center_region < 10000)]
            
            if len(valid_depths) > 100:  # Enough data points
                min_distance = float(np.min(valid_depths)) / 1000.0  # Convert to meters
                avg_distance = float(np.mean(valid_depths)) / 1000.0
                
                return {
                    'forward_min': round(min_distance, 2),
                    'forward_avg': round(avg_distance, 2),
                    'obstacle_detected': min_distance < 2.0
                }
            
        except Exception:
            pass
        
        return {'forward_min': 0, 'forward_avg': 0, 'obstacle_detected': False}

    def collect_telemetry_data(self):
        """Collect MAVLink telemetry data"""
        if not self.mavlink_connection:
            return
        
        print("Starting telemetry data collection...")
        
        while self.running:
            try:
                msg = self.mavlink_connection.recv_match(blocking=True, timeout=1.0)
                
                if msg:
                    msg_type = msg.get_type()
                    current_time = time.time()
                    
                    # Process different message types
                    if msg_type == 'GLOBAL_POSITION_INT':
                        telemetry_packet = {
                            'timestamp': current_time,
                            'type': 'position',
                            'lat': msg.lat / 1e7,
                            'lon': msg.lon / 1e7,
                            'alt': msg.alt / 1000.0,
                            'relative_alt': msg.relative_alt / 1000.0,
                            'vx': msg.vx / 100.0,
                            'vy': msg.vy / 100.0,
                            'vz': msg.vz / 100.0,
                            'hdg': msg.hdg / 100.0
                        }
                        
                    elif msg_type == 'ATTITUDE':
                        telemetry_packet = {
                            'timestamp': current_time,
                            'type': 'attitude',
                            'roll': msg.roll,
                            'pitch': msg.pitch,
                            'yaw': msg.yaw,
                            'rollspeed': msg.rollspeed,
                            'pitchspeed': msg.pitchspeed,
                            'yawspeed': msg.yawspeed
                        }
                        
                    elif msg_type == 'VFR_HUD':
                        telemetry_packet = {
                            'timestamp': current_time,
                            'type': 'hud',
                            'airspeed': msg.airspeed,
                            'groundspeed': msg.groundspeed,
                            'heading': msg.heading,
                            'throttle': msg.throttle,
                            'alt': msg.alt,
                            'climb': msg.climb
                        }
                        
                    elif msg_type == 'SYS_STATUS':
                        telemetry_packet = {
                            'timestamp': current_time,
                            'type': 'system_status',
                            'voltage_battery': msg.voltage_battery / 1000.0,
                            'current_battery': msg.current_battery / 100.0,
                            'battery_remaining': msg.battery_remaining,
                            'load': msg.load / 10.0
                        }
                    else:
                        continue
                    
                    try:
                        self.telemetry_queue.put_nowait(telemetry_packet)
                        self.system_status['pixhawk']['last_update'] = current_time
                    except queue.Full:
                        self.telemetry_queue.get()  # Remove oldest
                        self.telemetry_queue.put_nowait(telemetry_packet)
                
            except Exception as e:
                self.system_status['pixhawk']['error_count'] += 1
                print(f"Telemetry error: {e}")
                time.sleep(1)

    def relay_data_to_dashboard(self):
        """Send collected data to dashboard server"""
        print(f"Starting data relay to {self.dashboard_url}")
        
        while self.running:
            try:
                # Compile data packet
                data_packet = {
                    'timestamp': time.time(),
                    'rover_id': 'astra_nz_01',
                    'system_status': self.system_status,
                    'lidar_data': [],
                    'camera_data': None,
                    'telemetry_data': []
                }
                
                # Collect recent LiDAR data
                lidar_batch = []
                while not self.lidar_queue.empty() and len(lidar_batch) < 5:
                    try:
                        lidar_batch.append(self.lidar_queue.get_nowait())
                    except queue.Empty:
                        break
                data_packet['lidar_data'] = lidar_batch
                
                # Get latest camera data
                try:
                    data_packet['camera_data'] = self.camera_queue.get_nowait()
                except queue.Empty:
                    pass
                
                # Collect recent telemetry
                telemetry_batch = []
                while not self.telemetry_queue.empty() and len(telemetry_batch) < 10:
                    try:
                        telemetry_batch.append(self.telemetry_queue.get_nowait())
                    except queue.Empty:
                        break
                data_packet['telemetry_data'] = telemetry_batch
                
                # Send to dashboard
                if any([data_packet['lidar_data'], data_packet['camera_data'], data_packet['telemetry_data']]):
                    response = requests.post(
                        f"{self.dashboard_url}/api/rover_data",
                        json=data_packet,
                        timeout=3
                    )
                    
                    if response.status_code == 200:
                        self.system_status['dashboard']['connected'] = True
                        self.system_status['dashboard']['last_update'] = time.time()
                    else:
                        self.system_status['dashboard']['error_count'] += 1
                
                time.sleep(0.5)  # 2Hz relay rate
                
            except Exception as e:
                self.system_status['dashboard']['error_count'] += 1
                self.system_status['dashboard']['connected'] = False
                print(f"Dashboard relay error: {e}")
                time.sleep(2)

    def print_status_summary(self):
        """Print system status every 10 seconds"""
        while self.running:
            try:
                current_time = time.time()
                print("\n" + "="*60)
                print(f"Rover Data Relay Status - {datetime.now().strftime('%H:%M:%S')}")
                print("="*60)
                
                for sensor, status in self.system_status.items():
                    age = current_time - status['last_update'] if status['last_update'] > 0 else 999
                    conn_status = "✓" if status['connected'] and age < 10 else "✗"
                    
                    print(f"{sensor:12} {conn_status} | Errors: {status['error_count']:3} | "
                          f"Last: {age:4.1f}s ago")
                
                # Queue status
                print(f"\nQueues: LiDAR:{self.lidar_queue.qsize():2}/50 | "
                      f"Camera:{self.camera_queue.qsize():2}/10 | "
                      f"Telemetry:{self.telemetry_queue.qsize():2}/100")
                
                time.sleep(10)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Status error: {e}")
                time.sleep(10)

    def run(self):
        """Main execution function"""
        try:
            # Initialize all sensors
            self.initialize_sensors()
            
            # Start data collection threads
            threads = []
            
            if self.system_status['rplidar']['connected']:
                t1 = threading.Thread(target=self.collect_lidar_data, daemon=True)
                t1.start()
                threads.append(t1)
            
            if self.system_status['realsense']['connected']:
                t2 = threading.Thread(target=self.collect_camera_data, daemon=True)
                t2.start()
                threads.append(t2)
            
            if self.system_status['pixhawk']['connected']:
                t3 = threading.Thread(target=self.collect_telemetry_data, daemon=True)
                t3.start()
                threads.append(t3)
            
            # Start dashboard relay
            t4 = threading.Thread(target=self.relay_data_to_dashboard, daemon=True)
            t4.start()
            threads.append(t4)
            
            # Start status monitoring
            self.print_status_summary()
            
        except KeyboardInterrupt:
            print("\n\nShutdown requested...")
            self.shutdown()
        except Exception as e:
            print(f"System error: {e}")
            self.shutdown()

    def shutdown(self):
        """Clean shutdown of all systems"""
        print("Shutting down rover data relay...")
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
        
        print("Shutdown complete")

if __name__ == "__main__":
    relay_system = RoverDataRelay()
    relay_system.run()
