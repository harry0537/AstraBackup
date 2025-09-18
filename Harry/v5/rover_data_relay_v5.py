#!/usr/bin/env python3
"""
Project Astra NZ - Rover Data Relay v5
Based on working v5 proximity bridge methods
Handles resource sharing and optional dashboard
"""

import time
import sys
import json
import threading
import queue
import numpy as np
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sensor libraries with same imports as working v5
from rplidar import RPLidar
from pymavlink import mavutil

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

class RoverDataRelay:
    def __init__(self, dashboard_url="http://10.244.77.186:8080", enable_dashboard=True):
        # EXACT HARDWARE CONFIG FROM WORKING V5 PROXIMITY
        self.lidar_port = '/dev/ttyUSB0'
        self.pixhawk_port = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
        self.pixhawk_baud = 57600
        
        # Dashboard configuration
        self.dashboard_url = dashboard_url
        self.enable_dashboard = enable_dashboard
        self.dashboard_endpoint = f"{dashboard_url}/api/rover_data"
        
        # Sensor instances
        self.lidar = None
        self.realsense_pipeline = None
        self.mavlink = None
        
        # Threading and data management
        self.running = False
        self.lidar_thread_running = False
        self.lidar_data_lock = threading.Lock()
        
        # Data queues
        self.lidar_queue = queue.Queue(maxsize=50)
        self.camera_queue = queue.Queue(maxsize=10)
        self.telemetry_queue = queue.Queue(maxsize=100)
        
        # Statistics tracking
        self.stats = {
            'rplidar': {'success': 0, 'errors': 0, 'last_update': 0},
            'realsense': {'success': 0, 'errors': 0, 'last_update': 0},
            'pixhawk': {'success': 0, 'errors': 0, 'last_update': 0},
            'dashboard': {'success': 0, 'errors': 0, 'last_update': 0}
        }
        
        # HTTP session for dashboard with retries
        if self.enable_dashboard:
            self.session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        
        print("Project Astra NZ - Rover Data Relay v5")
        print("Using working v5 proximity sensor methods")
        if self.enable_dashboard:
            print(f"Dashboard: {self.dashboard_url}")
        else:
            print("Dashboard: DISABLED")
        print("=" * 60)

    def aggressive_buffer_clear(self):
        """EXACT COPY: Aggressively clear RPLidar buffers from working v5"""
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

    def connect_rplidar(self):
        """EXACT COPY: Working RPLidar connection from v5 proximity"""
        try:
            print("Connecting RPLidar S3...")
            self.lidar = RPLidar(self.lidar_port, baudrate=1000000, timeout=0.1)
            
            # Aggressive initial buffer clearing
            self.aggressive_buffer_clear()
            
            info = self.lidar.get_info()
            health = self.lidar.get_health()
            
            print(f"✓ RPLidar connected - Model: {info['model']}, Health: {health[0]}")
            return True
            
        except Exception as e:
            print(f"✗ RPLidar connection failed: {e}")
            self.stats['rplidar']['errors'] += 1
            self.lidar = None
            return False

    def connect_realsense(self):
        """SAFE RealSense connection - handles device busy gracefully"""
        if not REALSENSE_AVAILABLE:
            print("RealSense library not available")
            return False
            
        try:
            print("Connecting RealSense camera...")
            
            # Check if device is available
            ctx = rs.context()
            devices = ctx.query_devices()
            if len(devices) == 0:
                print("✗ No RealSense devices found")
                return False
            
            self.realsense_pipeline = rs.pipeline()
            config = rs.config()
            
            # EXACT CONFIG FROM WORKING V5: Lower resolution for better performance
            config.enable_stream(rs.stream.depth, 424, 240, rs.format.z16, 15)
            
            try:
                self.realsense_pipeline.start(config)
                
                # Warm up - same as working v5
                for _ in range(5):
                    self.realsense_pipeline.wait_for_frames()
                
                print("✓ RealSense connected successfully")
                return True
                
            except RuntimeError as e:
                if "busy" in str(e).lower() or "device or resource busy" in str(e).lower():
                    print("⚠ RealSense in use by another process (proximity bridge?)")
                    print("  Data relay will run without camera data")
                    if self.realsense_pipeline:
                        try:
                            self.realsense_pipeline.stop()
                        except:
                            pass
                    self.realsense_pipeline = None
                    return False
                raise e
            
        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            self.stats['realsense']['errors'] += 1
            if self.realsense_pipeline:
                try:
                    self.realsense_pipeline.stop()
                except:
                    pass
            self.realsense_pipeline = None
            return False

    def connect_pixhawk(self):
        """Working Pixhawk connection method from v5"""
        try:
            print("Connecting to Pixhawk...")
            self.mavlink = mavutil.mavlink_connection(
                self.pixhawk_port,
                baud=self.pixhawk_baud,
                source_system=1,
                source_component=196  # Different component ID from proximity bridge
            )
            
            self.mavlink.wait_heartbeat(timeout=10)
            print("✓ Pixhawk connected")
            return True
            
        except Exception as e:
            print(f"✗ Pixhawk connection failed: {e}")
            self.stats['pixhawk']['errors'] += 1
            self.mavlink = None
            return False

    def test_dashboard_connection(self):
        """Test dashboard connectivity"""
        if not self.enable_dashboard:
            return False
            
        try:
            response = self.session.get(self.dashboard_url, timeout=5)
            if response.status_code == 200:
                print("✓ Dashboard accessible")
                return True
            else:
                print(f"⚠ Dashboard returned status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠ Dashboard connection test failed: {e}")
            return False

    def lidar_data_thread(self):
        """EXACT COPY: LiDAR data collection from working v5 proximity"""
        print("Starting RPLidar data collection thread...")
        
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
                
                # CRITICAL: Uses iter_measurments (note typo in method name!)
                for measurement in self.lidar.iter_measurments():
                    if not self.lidar_thread_running:
                        break
                        
                    if len(measurement) >= 4:
                        _, quality, angle, distance = measurement[:4]
                        
                        if quality >= 10 and distance > 0:
                            scan_data.append({
                                'angle': angle,
                                'distance': distance,
                                'quality': quality,
                                'timestamp': time.time()
                            })
                    
                    measurement_count += 1
                    
                    # Quick exit - get data fast to prevent buffer buildup
                    if len(scan_data) > 50 and time.time() - start_time > 0.5:
                        break
                        
                    if measurement_count > 200 or time.time() - start_time > 1.0:
                        break
                
                # Add to queue if we got data
                if len(scan_data) > 10:
                    try:
                        self.lidar_queue.put({
                            'type': 'lidar_scan',
                            'data': scan_data,
                            'timestamp': time.time()
                        }, block=False)
                        
                        self.stats['rplidar']['success'] += 1
                        self.stats['rplidar']['last_update'] = time.time()
                        
                    except queue.Full:
                        # Remove old data if queue is full
                        try:
                            self.lidar_queue.get_nowait()
                            self.lidar_queue.put({
                                'type': 'lidar_scan',
                                'data': scan_data,
                                'timestamp': time.time()
                            }, block=False)
                        except:
                            pass
                
                # Stop motor to prevent buffer buildup
                try:
                    self.lidar.stop()
                except:
                    pass
                
                time.sleep(0.2)  # Brief pause between scans
                
            except Exception as e:
                print(f"LiDAR thread error: {e}")
                self.stats['rplidar']['errors'] += 1
                self.aggressive_buffer_clear()
                time.sleep(0.5)

    def realsense_data_thread(self):
        """RealSense data collection thread"""
        if not self.realsense_pipeline:
            return
            
        print("Starting RealSense data collection thread...")
        
        while self.running:
            try:
                frames = self.realsense_pipeline.wait_for_frames(timeout_ms=1000)
                depth_frame = frames.get_depth_frame()
                
                if depth_frame:
                    # Convert to numpy array
                    depth_image = np.asanyarray(depth_frame.get_data())
                    
                    # Sample key regions for data relay
                    height, width = depth_image.shape
                    center_region = depth_image[height//3:2*height//3, width//3:2*width//3]
                    
                    # Calculate statistics
                    valid_depths = center_region[(center_region > 100) & (center_region < 5000)]
                    
                    if len(valid_depths) > 10:
                        camera_data = {
                            'type': 'camera_depth',
                            'min_distance': float(np.min(valid_depths)),
                            'avg_distance': float(np.mean(valid_depths)),
                            'max_distance': float(np.max(valid_depths)),
                            'valid_pixels': len(valid_depths),
                            'timestamp': time.time()
                        }
                        
                        try:
                            self.camera_queue.put(camera_data, block=False)
                            self.stats['realsense']['success'] += 1
                            self.stats['realsense']['last_update'] = time.time()
                            
                        except queue.Full:
                            # Remove old data
                            try:
                                self.camera_queue.get_nowait()
                                self.camera_queue.put(camera_data, block=False)
                            except:
                                pass
                
                time.sleep(0.1)  # 10Hz data collection
                
            except Exception as e:
                print(f"RealSense thread error: {e}")
                self.stats['realsense']['errors'] += 1
                time.sleep(1)

    def telemetry_data_thread(self):
        """Pixhawk telemetry collection thread"""
        if not self.mavlink:
            return
            
        print("Starting telemetry data collection thread...")
        
        while self.running:
            try:
                # Request data streams
                self.mavlink.mav.request_data_stream_send(
                    self.mavlink.target_system,
                    self.mavlink.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    1, 1
                )
                
                # Collect telemetry
                msg = self.mavlink.recv_match(blocking=True, timeout=2)
                
                if msg:
                    telemetry_data = {
                        'type': 'telemetry',
                        'message_type': msg.get_type(),
                        'data': msg.to_dict(),
                        'timestamp': time.time()
                    }
                    
                    try:
                        self.telemetry_queue.put(telemetry_data, block=False)
                        self.stats['pixhawk']['success'] += 1
                        self.stats['pixhawk']['last_update'] = time.time()
                        
                    except queue.Full:
                        # Remove old data
                        try:
                            self.telemetry_queue.get_nowait()
                            self.telemetry_queue.put(telemetry_data, block=False)
                        except:
                            pass
                
            except Exception as e:
                print(f"Telemetry thread error: {e}")
                self.stats['pixhawk']['errors'] += 1
                time.sleep(1)

    def dashboard_relay_thread(self):
        """Send data to dashboard server"""
        if not self.enable_dashboard:
            return
            
        print(f"Starting dashboard relay thread to {self.dashboard_url}")
        
        while self.running:
            try:
                # Collect data from all queues
                relay_data = {
                    'rover_id': 'astra_nz_rover',
                    'timestamp': datetime.now().isoformat(),
                    'lidar_data': [],
                    'camera_data': [],
                    'telemetry_data': []
                }
                
                # Get LiDAR data
                while not self.lidar_queue.empty():
                    try:
                        relay_data['lidar_data'].append(self.lidar_queue.get_nowait())
                    except:
                        break
                
                # Get camera data
                while not self.camera_queue.empty():
                    try:
                        relay_data['camera_data'].append(self.camera_queue.get_nowait())
                    except:
                        break
                
                # Get telemetry data
                while not self.telemetry_queue.empty():
                    try:
                        relay_data['telemetry_data'].append(self.telemetry_queue.get_nowait())
                    except:
                        break
                
                # Send to dashboard if we have data
                if (relay_data['lidar_data'] or 
                    relay_data['camera_data'] or 
                    relay_data['telemetry_data']):
                    
                    response = self.session.post(
                        self.dashboard_endpoint,
                        json=relay_data,
                        timeout=3
                    )
                    
                    if response.status_code == 200:
                        self.stats['dashboard']['success'] += 1
                        self.stats['dashboard']['last_update'] = time.time()
                    else:
                        raise Exception(f"Dashboard returned {response.status_code}")
                
                time.sleep(1)  # 1Hz dashboard updates
                
            except Exception as e:
                print(f"Dashboard relay error: {e}")
                self.stats['dashboard']['errors'] += 1
                time.sleep(2)

    def print_status(self):
        """Print system status"""
        while self.running:
            try:
                current_time = time.time()
                
                print("\n" + "=" * 60)
                print(f"Rover Data Relay Status - {time.strftime('%H:%M:%S')}")
                print("=" * 60)
                
                for sensor, stats in self.stats.items():
                    last_update = current_time - stats['last_update']
                    if last_update > 600:  # More than 10 minutes
                        last_str = "999.0s ago"
                        status = "✗"
                    else:
                        last_str = f"{last_update:5.1f}s ago"
                        status = "✓" if last_update < 30 else "⚠"
                    
                    print(f"{sensor:12} {status} | Errors: {stats['errors']:3} | Last: {last_str}")
                
                # Queue status
                lidar_size = self.lidar_queue.qsize()
                camera_size = self.camera_queue.qsize()
                telemetry_size = self.telemetry_queue.qsize()
                
                print(f"Queues: LiDAR: {lidar_size}/50 | Camera:{camera_size:2}/10 | Telemetry:{telemetry_size:3}/100")
                
                time.sleep(10)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Status error: {e}")
                time.sleep(10)

    def run(self):
        """Main execution loop"""
        print("Initializing sensors...")
        
        # Connect to all devices
        lidar_ok = self.connect_rplidar()
        realsense_ok = self.connect_realsense()
        pixhawk_ok = self.connect_pixhawk()
        dashboard_ok = self.test_dashboard_connection() if self.enable_dashboard else False
        
        if not (lidar_ok or realsense_ok or pixhawk_ok):
            print("ERROR: No sensors connected successfully")
            return False
        
        # Start all threads
        self.running = True
        threads = []
        
        # LiDAR thread
        if lidar_ok:
            self.lidar_thread_running = True
            thread = threading.Thread(target=self.lidar_data_thread, daemon=True)
            thread.start()
            threads.append(thread)
        
        # RealSense thread
        if realsense_ok:
            thread = threading.Thread(target=self.realsense_data_thread, daemon=True)
            thread.start()
            threads.append(thread)
        
        # Telemetry thread
        if pixhawk_ok:
            thread = threading.Thread(target=self.telemetry_data_thread, daemon=True)
            thread.start()
            threads.append(thread)
        
        # Dashboard relay thread
        if self.enable_dashboard:
            thread = threading.Thread(target=self.dashboard_relay_thread, daemon=True)
            thread.start()
            threads.append(thread)
        
        print("\nStarting data relay...")
        print("Press Ctrl+C to stop")
        
        try:
            self.print_status()
        except KeyboardInterrupt:
            print("\nStopping data relay...")
        finally:
            self.cleanup()

    def cleanup(self):
        """EXACT COPY: Clean shutdown from working v5"""
        print("Shutting down data relay...")
        self.running = False
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
        
        if hasattr(self, 'session'):
            try:
                self.session.close()
                print("Dashboard session closed")
            except:
                pass
        
        print("Shutdown complete")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Rover Data Relay v5')
    parser.add_argument('--dashboard', default='http://10.244.77.186:8080', 
                       help='Dashboard URL')
    parser.add_argument('--no-dashboard', action='store_true',
                       help='Disable dashboard connection')
    
    args = parser.parse_args()
    
    enable_dashboard = not args.no_dashboard
    
    relay = RoverDataRelay(
        dashboard_url=args.dashboard,
        enable_dashboard=enable_dashboard
    )
    relay.run()
