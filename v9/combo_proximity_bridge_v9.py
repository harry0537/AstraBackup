#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V9
NO CAMERA ACCESS - Reads depth from Vision Server
Component 195 - Modified for V9 Architecture
"""

import time
import threading
import numpy as np
import json
import os
import sys
from rplidar import RPLidar
from pymavlink import mavutil

# Hardware configuration - Load from config file
def load_hardware_config():
    """Load hardware configuration from rover_config_v9.json"""
    config_file = "rover_config_v9.json"
    default_config = {
        'lidar_port': '/dev/ttyUSB0',
        'pixhawk_port': '/dev/ttyACM0'
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                print(f"[CONFIG] Loaded hardware config from {config_file}")
                return {
                    'lidar_port': config.get('lidar_port', default_config['lidar_port']),
                    'pixhawk_port': config.get('pixhawk_port', default_config['pixhawk_port'])
                }
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}, using defaults")

    print("[WARNING] Using default hardware configuration")
    return default_config

# Load hardware configuration
HARDWARE_CONFIG = load_hardware_config()
LIDAR_PORT = HARDWARE_CONFIG['lidar_port']
PIXHAWK_PORT = HARDWARE_CONFIG['pixhawk_port']
PIXHAWK_BAUD = 57600
COMPONENT_ID = 195

# Vision Server paths
VISION_SERVER_DIR = "/tmp/vision_v9"
DEPTH_FILE = os.path.join(VISION_SERVER_DIR, "depth_latest.bin")
DEPTH_META_FILE = os.path.join(VISION_SERVER_DIR, "depth_latest.json")
VISION_STATUS_FILE = os.path.join(VISION_SERVER_DIR, "status.json")


class ComboProximityBridge:
    def __init__(self):
        self.lidar = None
        self.mavlink = None
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
            'start_time': time.time(),
            'lidar_errors': 0,
            'last_lidar_error': None,
            'vision_server_errors': 0
        }

        # Track stderr for lidar warnings
        self.original_stderr = sys.stderr
        self.stderr_redirected = False
        self.devnull_file = None

        # Suppress rplidar buffer warnings
        self.suppress_warnings = True
        self.lidar_retry_count = 0
        self.max_lidar_retries = 5

        # Vision Server tracking
        self.last_depth_frame_number = 0
        self.vision_server_available = False

    def check_vision_server(self):
        """Check if Vision Server is running and providing data."""
        try:
            if not os.path.exists(VISION_STATUS_FILE):
                return False
            
            with open(VISION_STATUS_FILE, 'r') as f:
                status = json.load(f)
            
            # Check if status is recent (< 5 seconds old)
            age = time.time() - status.get('timestamp', 0)
            if age > 5.0:
                return False
            
            # Check if Vision Server is running
            if status.get('status') != 'RUNNING':
                return False
            
            return True
        except:
            return False

    def read_depth_from_vision_server(self):
        """Read depth data from Vision Server files.
        
        Returns:
            depth_frame: numpy array of depth values (uint16, millimeters)
            metadata: dict with frame info
            success: bool
        """
        try:
            # Check if metadata file exists
            if not os.path.exists(DEPTH_META_FILE):
                return None, None, False
            
            # Read metadata first
            with open(DEPTH_META_FILE, 'r') as f:
                meta = json.load(f)
            
            # Validate metadata has required fields
            if 'timestamp' not in meta or 'frame_number' not in meta:
                return None, None, False
            
            # Check if data is fresh (< 1 second old)
            age = time.time() - meta['timestamp']
            if age > 1.0:
                return None, None, False
            
            # Check if we already processed this frame
            if meta['frame_number'] == self.last_depth_frame_number:
                return None, None, False  # Same frame, skip
            
            # Read binary depth data
            width = meta.get('width', 424)
            height = meta.get('height', 240)
            
            # Check if depth file exists
            if not os.path.exists(DEPTH_FILE):
                return None, None, False
            
            # Read binary file
            depth_array = np.fromfile(DEPTH_FILE, dtype=np.uint16)
            
            # Validate size
            expected_size = width * height
            if len(depth_array) != expected_size:
                print(f"[ERROR] Depth data size mismatch: {len(depth_array)} != {expected_size}")
                return None, None, False
            
            # Reshape to 2D array
            depth_frame = depth_array.reshape((height, width))
            
            # Update frame tracking
            self.last_depth_frame_number = meta['frame_number']
            
            return depth_frame, meta, True
            
        except FileNotFoundError:
            return None, None, False
        except json.JSONDecodeError:
            # Corrupted JSON file
            return None, None, False
        except (ValueError, TypeError, KeyError) as e:
            # Invalid metadata format
            self.stats['vision_server_errors'] += 1
            return None, None, False
        except Exception as e:
            self.stats['vision_server_errors'] += 1
            return None, None, False

    def connect_lidar(self):
        """Connect to RPLidar S3 - UNCHANGED from V8"""
        for attempt in range(self.max_lidar_retries):
            try:
                print(f"Connecting RPLidar at {LIDAR_PORT} (attempt {attempt + 1}/{self.max_lidar_retries})")
                self.lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=2)

                info = self.lidar.get_info()
                health = self.lidar.get_health()
                print(f"[OK] RPLidar S3: Model {info['model']}, Health {health[0]}")
                print("  [NOTE] Buffer warnings are from rplidar library (known issue)")
                self.lidar_retry_count = 0
                return True

            except Exception as e:
                self.stats['lidar_errors'] += 1
                self.stats['last_lidar_error'] = str(e)
                print(f"[ERROR] RPLidar attempt {attempt + 1} failed: {e}")

                if self.lidar:
                    try:
                        self.lidar.disconnect()
                    except:
                        pass
                    self.lidar = None

                if attempt < self.max_lidar_retries - 1:
                    print(f"  [RETRY] Waiting 2 seconds before retry...")
                    time.sleep(2)
                else:
                    print(f"  [FAILED] All {self.max_lidar_retries} attempts failed")
                    return False

        return False

    def connect_pixhawk(self):
        """Connect to Pixhawk via MAVLink - UNCHANGED from V8"""
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
                    print(f"  [MAVLink] System ID: {self.mavlink.target_system}, Component ID: {self.mavlink.target_component}")
                    return True
                except Exception as e:
                    print(f"  [FAILED] {port}: {e}")
                    self.mavlink = None

            raise RuntimeError('No Pixhawk port available')

        except Exception as e:
            print(f"✗ Pixhawk failed: {e}")
            return False

    def lidar_thread(self):
        """LiDAR thread - UNCHANGED from V8"""
        
        # Redirect stderr to suppress library warnings
        if self.suppress_warnings:
            try:
                self.devnull_file = open(os.devnull, 'w')
                sys.stderr = self.devnull_file
                self.stderr_redirected = True
            except:
                pass

        try:
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

                except Exception as e:
                    self.stats['lidar_errors'] += 1
                    self.stats['last_lidar_error'] = str(e)

                    # Restore stderr temporarily for error reporting
                    if self.stderr_redirected:
                        sys.stderr = self.original_stderr
                    print(f"[LIDAR] Thread error: {e}")
                    if self.stderr_redirected:
                        sys.stderr = self.devnull_file

                    try:
                        self.lidar.stop()
                        self.lidar.stop_motor()
                    except:
                        pass

                    # Try to reconnect if too many errors
                    if self.stats['lidar_errors'] > 10:
                        if self.stderr_redirected:
                            sys.stderr = self.original_stderr
                        print("[LIDAR] Too many errors, attempting reconnection...")
                        if self.stderr_redirected:
                            sys.stderr = self.devnull_file

                        try:
                            self.lidar.disconnect()
                        except:
                            pass
                        self.lidar = None
                        time.sleep(5)
                        if self.connect_lidar():
                            self.stats['lidar_errors'] = 0
                    else:
                        time.sleep(1)

        finally:
            # Always restore stderr and close devnull
            if self.stderr_redirected:
                sys.stderr = self.original_stderr
                self.stderr_redirected = False
            if self.devnull_file:
                try:
                    self.devnull_file.close()
                except:
                    pass
                self.devnull_file = None

    def realsense_thread_v9(self):
        """RealSense thread - V9: Reads from Vision Server instead of camera."""
        
        consecutive_failures = 0
        max_failures = 10
        
        while self.running:
            try:
                # Read depth from Vision Server
                depth_frame, meta, success = self.read_depth_from_vision_server()
                
                if not success:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        if not self.vision_server_available:
                            print("[REALSENSE] Vision Server unavailable, using LiDAR-only mode")
                            self.vision_server_available = False
                        consecutive_failures = 0  # Reset to avoid spam
                    time.sleep(0.1)
                    continue
                
                # Mark Vision Server as available
                if not self.vision_server_available:
                    print("[REALSENSE] ✓ Vision Server connected")
                    self.vision_server_available = True
                
                # Reset failure counter on success
                consecutive_failures = 0
                
                # Process depth data (SAME LOGIC AS V8)
                width = meta['width']
                height = meta['height']
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
                    # Bounds check for array access
                    y_start = max(0, y1)
                    y_end = min(height, y2 - (y2 - y1)//3)
                    x_start = max(0, x1)
                    x_end = min(width, x2)
                    
                    for y in range(y_start, y_end, step):
                        for x in range(x_start, x_end, step):
                            try:
                                # Depth value in millimeters (uint16)
                                d_mm = depth_frame[y, x]
                                d_m = d_mm / 1000.0
                                if 0.2 < d_m < 25.0:
                                    depths.append(d_m)
                            except IndexError:
                                # Skip invalid coordinates
                                continue
                    
                    if len(depths) > 30:
                        try:
                            closest_m = float(np.percentile(depths, 5))
                            closest_cm = max(self.min_distance_cm,
                                           min(int(closest_m * 100), self.max_distance_cm))
                            sectors[forward_sectors[i]] = closest_cm
                        except (ValueError, IndexError):
                            # Failed to compute percentile
                            pass
                
                with self.lock:
                    self.realsense_sectors = sectors
                self.stats['realsense_success'] += 1
                
                time.sleep(0.03)  # ~30Hz
                
            except Exception as e:
                print(f"[REALSENSE] Thread error: {e}")
                consecutive_failures += 1
                time.sleep(0.1)

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

        # Send to Pixhawk (EXACTLY as v8)
        orientations = [0, 1, 2, 3, 4, 5, 6, 7]
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        
        # Debug: Print first few sends to verify format
        debug_sent = False
        
        for sector_id, distance_cm in enumerate(fused):
            try:
                # Send exactly as v8 does - no extra validation
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
                
                # Debug output for first batch only
                if not debug_sent and sector_id < 3:
                    print(f"[DEBUG] Sent sector {sector_id}: {int(distance_cm)}cm, orientation={orientations[sector_id]}, type=0")
                    if sector_id == 2:
                        debug_sent = True
                        
            except Exception as e:
                # Log first error for debugging
                if sector_id == 0:
                    print(f"[ERROR] Failed to send DISTANCE_SENSOR sector 0: {e}")

        self.stats['messages_sent'] += self.num_sectors

        # Publish status
        try:
            payload = {
                'timestamp': time.time(),
                'sectors_cm': fused,
                'min_cm': int(min(fused)),
                'lidar_cm': lidar,
                'realsense_cm': rsc,
                'messages_sent': self.stats['messages_sent'],
                'lidar_errors': self.stats['lidar_errors'],
                'last_lidar_error': self.stats['last_lidar_error'],
                'vision_server_available': self.vision_server_available
            }
            with open('/tmp/proximity_v9.json.tmp', 'w') as f:
                json.dump(payload, f)
            os.replace('/tmp/proximity_v9.json.tmp', '/tmp/proximity_v9.json')
        except:
            pass

    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        l_rate = int((self.stats['lidar_success'] / max(1, self.stats['lidar_attempts'])) * 100)

        with self.lock:
            lidar_min = min(self.lidar_sectors)
            rs_min = min(self.realsense_sectors)
            # Get sample of fused data for debugging
            lidar_sample = self.lidar_sectors[:3]
            rs_sample = self.realsense_sectors[:3]

        # Status display
        vision_status = "✓" if self.vision_server_available else "✗"
        error_info = f" E:{self.stats['lidar_errors']}" if self.stats['lidar_errors'] > 0 else ""
        mavlink_status = "✓" if self.mavlink else "✗"
        
        # Calculate messages per second
        elapsed = max(1, uptime)
        msg_rate = self.stats['messages_sent'] / elapsed
        
        # Show sample data every 5 seconds for debugging
        debug_info = ""
        if uptime % 5 == 0:
            debug_info = f" | L[{lidar_sample[0]/100:.1f},{lidar_sample[1]/100:.1f},{lidar_sample[2]/100:.1f}] R[{rs_sample[0]/100:.1f},{rs_sample[1]/100:.1f},{rs_sample[2]/100:.1f}]"
        
        print(f"\r[{uptime:3d}s] "
              f"MAV:{mavlink_status} Vision:{vision_status} Forward(RS):{rs_min/100:.1f}m | "
              f"Lidar:{l_rate:2d}% {lidar_min/100:.1f}m{error_info} | "
              f"TX:{self.stats['messages_sent']:5d} ({msg_rate:.1f}/s){debug_info}", end='', flush=True)

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V9 (NO CAMERA ACCESS)")
        print("=" * 60)
        print(f"[CONFIG] LIDAR Port: {LIDAR_PORT}")
        print(f"[CONFIG] Pixhawk Port: {PIXHAWK_PORT}")
        print(f"[V9] Vision Server: {VISION_SERVER_DIR}")
        print("=" * 60)

        # Check for Vision Server
        print("\nWaiting for Vision Server (max 30 seconds)...")
        vision_server_ready = False
        for i in range(30):
            if self.check_vision_server():
                vision_server_ready = True
                print("✓ Vision Server detected and running")
                break
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"  Still waiting... ({i}/30 seconds)")
        
        if not vision_server_ready:
            print("⚠ Vision Server not detected after 30 seconds")
            print("  Will run in LiDAR-only mode")
            print("  To start Vision Server:")
            print("    python3 realsense_vision_server_v9.py")

        # Connect to Pixhawk (REQUIRED)
        pixhawk_ok = self.connect_pixhawk()
        if not pixhawk_ok:
            print("\n[ERROR] Cannot continue without Pixhawk")
            return

        # Connect to LiDAR (BEST EFFORT)
        lidar_ok = self.connect_lidar()

        if not lidar_ok and not vision_server_ready:
            print("\n[ERROR] At least one sensor (Vision Server or LiDAR) is required")
            return

        # Start threads
        if lidar_ok:
            threading.Thread(target=self.lidar_thread, daemon=True).start()
            print("[OK] LIDAR thread started")
        else:
            print("[WARNING] LIDAR not available - using Vision Server only")

        if vision_server_ready:
            threading.Thread(target=self.realsense_thread_v9, daemon=True).start()
            print("[OK] RealSense thread started (reading from Vision Server)")

        print("\n[OK] Proximity bridge operational - V9 MODE")
        if vision_server_ready and lidar_ok:
            print("  • PRIMARY: Vision Server depth (forward 135° arc)")
            print("  • SECONDARY: LiDAR (side/rear, best effort)")
        elif vision_server_ready:
            print("  • PRIMARY: Vision Server depth only (forward 135° arc)")
            print("  • LIDAR: Not available (limited side/rear coverage)")
        else:
            print("  • PRIMARY: LiDAR only (360° coverage)")
            print("  • Vision Server: Not available (forward arc limited)")
        print("  • Update: 10Hz to Mission Planner\n")

        try:
            last_send = time.time()
            last_status = time.time()
            last_heartbeat_check = time.time()

            while self.running:
                # Send proximity data at 10Hz (every 0.1 seconds)
                if time.time() - last_send > 0.1:
                    # Verify MAVLink connection is still alive
                    if self.mavlink:
                        try:
                            # Keep connection alive by reading pending messages
                            self.mavlink.recv_match(blocking=False, timeout=0.01)
                        except:
                            # Connection might be broken, try to reconnect
                            print("[WARNING] MAVLink connection lost, attempting reconnect...")
                            if not self.connect_pixhawk():
                                print("[ERROR] Failed to reconnect to Pixhawk")
                                break
                    
                    self.fuse_and_send()
                    last_send = time.time()

                # Check for heartbeat from Pixhawk every 5 seconds
                if self.mavlink and time.time() - last_heartbeat_check > 5.0:
                    try:
                        # Try to get a heartbeat message
                        msg = self.mavlink.recv_match(type='HEARTBEAT', blocking=False, timeout=0.1)
                        if msg:
                            last_heartbeat_check = time.time()
                    except:
                        # Connection might be broken
                        pass

                # Print status every 1 second
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Initiated...")

        finally:
            self.running = False

            if self.lidar:
                try:
                    self.lidar.stop()
                    self.lidar.stop_motor()
                    self.lidar.disconnect()
                except:
                    pass

            # Restore stderr and close devnull
            if self.stderr_redirected:
                sys.stderr = self.original_stderr
                self.stderr_redirected = False
            if self.devnull_file:
                try:
                    self.devnull_file.close()
                except:
                    pass
                self.devnull_file = None

            print("[OK] Proximity bridge stopped")


if __name__ == "__main__":
    bridge = ComboProximityBridge()
    bridge.run()

