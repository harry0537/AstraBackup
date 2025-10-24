#!/usr/bin/env python3
"""
Project Astra NZ - Combo Proximity Bridge V8
Accepts rplidar library buffer limitations, focuses on RealSense reliability
Component 195 - Production Ready - Bug Fixes from V7
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

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARNING] cv2 not available - color frame saving disabled")

# Hardware configuration - Load from config file
def load_hardware_config():
    """Load hardware configuration from rover_config_v8.json"""
    config_file = "rover_config_v8.json"
    default_config = {
        'lidar_port': '/dev/ttyUSB0',
        'pixhawk_port': '/dev/ttyACM0',
        'realsense_config': {'width': 424, 'height': 240, 'fps': 15}
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                print(f"[CONFIG] Loaded hardware config from {config_file}")
                return {
                    'lidar_port': config.get('lidar_port', default_config['lidar_port']),
                    'pixhawk_port': config.get('pixhawk_port', default_config['pixhawk_port']),
                    'realsense_config': config.get('realsense_config', default_config['realsense_config'])
                }
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}, using defaults")

    print("[WARNING] Using default hardware configuration")
    return default_config

# Load hardware configuration
HARDWARE_CONFIG = load_hardware_config()
LIDAR_PORT = HARDWARE_CONFIG['lidar_port']
PIXHAWK_PORT = HARDWARE_CONFIG['pixhawk_port']
REALSENSE_CONFIG = HARDWARE_CONFIG['realsense_config']
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
            'start_time': time.time(),
            'lidar_errors': 0,
            'last_lidar_error': None
        }

        # FIX BUG #8: Track stderr state for proper restoration
        self.original_stderr = sys.stderr
        self.stderr_redirected = False
        self.devnull_file = None  # FIX BUG #15: Store devnull handle to prevent FD leak

        # Suppress rplidar buffer warnings
        self.suppress_warnings = True
        self.lidar_retry_count = 0
        self.max_lidar_retries = 5

        # RealSense retry settings
        self.realsense_retry_count = 0
        self.max_realsense_retries = 3
        
        # RGB exposure control (adaptive manual)
        self.rgb_sensor = None
        self.exposure_us = 6000.0
        self.gain_value = 32.0
        self.exposure_min = 500.0
        self.exposure_max = 20000.0
        self.gain_min = 8.0
        self.gain_max = 64.0
        self.exposure_step = 500.0
        self.last_exposure_update = 0.0
        # Brightness targets in [0..255]
        self.target_brightness_low = 70
        self.target_brightness_high = 150

    def adjust_rgb_exposure(self, mean_brightness: float) -> None:
        """Simple adaptive exposure: keep brightness between low/high.
        Adjusts exposure (primary) and gain (secondary) with gentle steps.
        Safe no-op if sensor/options unavailable."""
        if not CV2_AVAILABLE or self.rgb_sensor is None:
            return
        now = time.time()
        if now - self.last_exposure_update < 0.4:  # limit update rate
            return
        try:
            if mean_brightness > self.target_brightness_high:
                # Too bright → reduce exposure, then gain
                if self.rgb_sensor.supports(rs.option.exposure):
                    self.exposure_us = max(self.exposure_min, self.exposure_us - self.exposure_step)
                    self.rgb_sensor.set_option(rs.option.exposure, float(self.exposure_us))
                if self.rgb_sensor.supports(rs.option.gain):
                    self.gain_value = max(self.gain_min, self.gain_value - 2.0)
                    self.rgb_sensor.set_option(rs.option.gain, float(self.gain_value))
            elif mean_brightness < self.target_brightness_low:
                # Too dark → increase exposure, then gain
                if self.rgb_sensor.supports(rs.option.exposure):
                    self.exposure_us = min(self.exposure_max, self.exposure_us + self.exposure_step)
                    self.rgb_sensor.set_option(rs.option.exposure, float(self.exposure_us))
                if self.rgb_sensor.supports(rs.option.gain):
                    self.gain_value = min(self.gain_max, self.gain_value + 2.0)
                    self.rgb_sensor.set_option(rs.option.gain, float(self.gain_value))
            # else inside band → no change
        except Exception:
            pass
        finally:
            self.last_exposure_update = now

    def configure_color_exposure(self, profile):
        """Reduce daytime overexposure on RGB stream (manual exposure).
        Tries to set safe, daylight-friendly values; silently ignores unsupported options."""
        try:
            device = profile.get_device()
            sensors = device.query_sensors()
            for s in sensors:
                try:
                    name = s.get_info(rs.camera_info.name) if hasattr(rs, 'camera_info') else ''
                except Exception:
                    name = ''
                # Prefer the RGB camera but apply to any sensor that supports the options
                if hasattr(s, 'supports') and (name.lower().find('rgb') != -1 or True):
                    try:
                        if s.supports(rs.option.enable_auto_exposure):
                            s.set_option(rs.option.enable_auto_exposure, 0)  # manual
                        if s.supports(rs.option.exposure):
                            # 6000-8000 us is generally good for daylight; start conservative
                            self.exposure_us = 6000.0
                            s.set_option(rs.option.exposure, float(self.exposure_us))
                        if s.supports(rs.option.gain):
                            self.gain_value = 32.0
                            s.set_option(rs.option.gain, float(self.gain_value))
                        if s.supports(rs.option.auto_exposure_priority):
                            s.set_option(rs.option.auto_exposure_priority, 0.0)
                        if s.supports(rs.option.backlight_compensation):
                            s.set_option(rs.option.backlight_compensation, 1.0)
                        print("  [RGB] Applied manual exposure (6000us, gain 32, BLC on)")
                        self.rgb_sensor = s
                        break
                    except Exception:
                        continue
        except Exception:
            # Non-fatal; continue with defaults
            pass

    def connect_lidar(self):
        """Connect to RPLidar S3 - IMPROVED with retry logic"""
        for attempt in range(self.max_lidar_retries):
            try:
                print(f"Connecting RPLidar at {LIDAR_PORT} (attempt {attempt + 1}/{self.max_lidar_retries})")
                self.lidar = RPLidar(LIDAR_PORT, baudrate=1000000, timeout=2)

                info = self.lidar.get_info()
                health = self.lidar.get_health()
                print(f"[OK] RPLidar S3: Model {info['model']}, Health {health[0]}")
                print("  [NOTE] Buffer warnings are from rplidar library (known issue)")
                self.lidar_retry_count = 0  # Reset on success
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

    def connect_realsense(self):
        """Connect to Intel RealSense D435i - PRIMARY SENSOR with proper initialization"""
        try:
            if not REALSENSE_AVAILABLE:
                print("[ERROR] RealSense library not available")
                return False

            print("Connecting RealSense D435i (PRIMARY forward sensor)")

            # Create pipeline and config
            self.pipeline = rs.pipeline()
            config = rs.config()

            # Use detected configuration first, then fallbacks
            detected_config = REALSENSE_CONFIG
            configs_to_try = [
                # Use detected configuration first (depth + color for streaming)
                (detected_config['width'], detected_config['height'], detected_config['fps']),
                # Fallback configurations
                (424, 240, 15),
                (640, 480, 15),
                (848, 480, 15),
            ]

            connected = False
            for i, (width, height, fps) in enumerate(configs_to_try):
                try:
                    print(f"  [CONFIG] Trying {width}x{height} @ {fps}fps (depth + color)...")
                    config = rs.config()
                    # Enable both depth and color streams
                    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
                    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
                    profile = self.pipeline.start(config)

                    # Configure RGB exposure to avoid day overexposure
                    self.configure_color_exposure(profile)

                    # Wait for camera to stabilize
                    print("  [INIT] Stabilizing camera...")
                    time.sleep(2)

                    # Test frame capture with multiple attempts
                    print("  [TEST] Testing frame capture...")
                    for attempt in range(10):
                        try:
                            frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                            depth_frame = frames.get_depth_frame()
                            if depth_frame:
                                print(f"[OK] RealSense D435i connected - {width}x{height} @ {fps}fps")
                                return True
                        except Exception as e:
                            if attempt < 9:
                                print(f"    [RETRY] Frame attempt {attempt+1}/10...")
                                time.sleep(0.5)
                            continue

                    # If we get here, this config didn't work
                    print(f"  [FAILED] Config {i+1} didn't work, trying next...")
                    self.pipeline.stop()
                    time.sleep(1)

                except Exception as e:
                    print(f"  [ERROR] Config {i+1} failed: {e}")
                    if self.pipeline:
                        try:
                            self.pipeline.stop()
                        except:
                            pass
                    time.sleep(1)
                    continue

            print("[ERROR] All RealSense configurations failed")
            self.pipeline = None
            return False

        except Exception as e:
            print(f"[ERROR] RealSense connection failed: {e}")
            self.pipeline = None
            return False

    def reset_realsense(self):
        """Reset RealSense camera by stopping and restarting"""
        try:
            if self.pipeline:
                print("  [RESET] Stopping RealSense pipeline...")
                self.pipeline.stop()
                time.sleep(2)
                self.pipeline = None
            print("  [RESET] RealSense reset complete")
            return True
        except Exception as e:
            print(f"  [ERROR] RealSense reset failed: {e}")
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

        # FIX BUG #8/#15: Open devnull once and reuse to prevent FD leak
        # Redirect stderr to suppress library warnings if requested
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

                    # FIX BUG #15: Restore stderr temporarily for error reporting, reuse devnull handle
                    if self.stderr_redirected:
                        sys.stderr = self.original_stderr
                    print(f"[LIDAR] Thread error: {e}")
                    if self.stderr_redirected:
                        sys.stderr = self.devnull_file  # Reuse existing handle

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
                            sys.stderr = self.devnull_file  # Reuse existing handle

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
            # FIX BUG #8/#15: Always restore stderr and close devnull handle
            if self.stderr_redirected:
                sys.stderr = self.original_stderr
                self.stderr_redirected = False
            if self.devnull_file:
                try:
                    self.devnull_file.close()
                except:
                    pass
                self.devnull_file = None

    def realsense_thread(self):
        """RealSense - PRIMARY sensor for forward detection"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue

            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=500)
                depth_frame = frames.get_depth_frame()
                color_frame = frames.get_color_frame()  # Also get color frame for streaming
                
                if not depth_frame:
                    time.sleep(0.03)
                    continue

                # Save color frame for streaming component (atomic write)
                if color_frame and CV2_AVAILABLE:
                    try:
                        color_image = np.asanyarray(color_frame.get_data())
                        # Adaptive exposure: compute mean brightness on grayscale
                        try:
                            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
                            mean_val = float(np.mean(gray))
                            self.adjust_rgb_exposure(mean_val)
                        except Exception:
                            pass
                        tmp_path = '/tmp/realsense_latest.jpg.tmp'
                        out_path = '/tmp/realsense_latest.jpg'
                        ok = cv2.imwrite(tmp_path, color_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ok:
                            try:
                                os.replace(tmp_path, out_path)
                            except Exception:
                                # If atomic replace fails, fall back to simple write
                                cv2.imwrite(out_path, color_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    except Exception:
                        pass  # Silent fail - streaming is optional

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
                'messages_sent': self.stats['messages_sent'],
                'lidar_errors': self.stats['lidar_errors'],
                'last_lidar_error': self.stats['last_lidar_error']
            }
            with open('/tmp/proximity_v8.json.tmp', 'w') as f:
                json.dump(payload, f)
            os.replace('/tmp/proximity_v8.json.tmp', '/tmp/proximity_v8.json')
        except:
            pass

    def print_status(self):
        """Print system status"""
        uptime = int(time.time() - self.stats['start_time'])
        l_rate = int((self.stats['lidar_success'] / max(1, self.stats['lidar_attempts'])) * 100)

        with self.lock:
            lidar_min = min(self.lidar_sectors)
            rs_min = min(self.realsense_sectors)

        # Clean status with error info
        error_info = f" E:{self.stats['lidar_errors']}" if self.stats['lidar_errors'] > 0 else ""
        if self.pipeline:
            print(f"\r[{uptime:3d}s] "
                  f"Forward(RS):{rs_min/100:.1f}m [OK] | "
                  f"Lidar:{l_rate:2d}% {lidar_min/100:.1f}m{error_info} | "
                  f"TX:{self.stats['messages_sent']:5d}", end='', flush=True)
        else:
            print(f"\r[{uptime:3d}s] "
                  f"LIDAR-ONLY:{l_rate:2d}% {lidar_min/100:.1f}m{error_info} | "
                  f"TX:{self.stats['messages_sent']:5d}", end='', flush=True)

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Combo Proximity Bridge V8 - Production (Bug Fixes)")
        print("=" * 60)
        print(f"[CONFIG] LIDAR Port: {LIDAR_PORT}")
        print(f"[CONFIG] Pixhawk Port: {PIXHAWK_PORT}")
        print("=" * 60)

        pixhawk_ok = self.connect_pixhawk()
        lidar_ok = self.connect_lidar()

        # Try RealSense with retry logic
        realsense_ok = False
        if REALSENSE_AVAILABLE:
            for attempt in range(self.max_realsense_retries):
                print(f"\n[REALSENSE] Attempt {attempt + 1}/{self.max_realsense_retries}")
                realsense_ok = self.connect_realsense()
                if realsense_ok:
                    break
                else:
                    if attempt < self.max_realsense_retries - 1:
                        print(f"[RETRY] Waiting 3 seconds before retry...")
                        self.reset_realsense()
                        time.sleep(3)
        else:
            print("[ERROR] RealSense library not available")

        if not pixhawk_ok:
            print("[ERROR] Cannot continue without Pixhawk")
            return

        # FIX BUG #3: Allow LIDAR-only mode, clarify error message
        if not realsense_ok and not lidar_ok:
            print("[ERROR] At least one sensor (RealSense or LIDAR) is required")
            print("  [NOTE] Both sensors are recommended for optimal coverage")
            return
        elif not realsense_ok:
            print("[WARNING] RealSense not available - using LIDAR-only mode")
            print("  [NOTE] Forward coverage may be limited without RealSense")

        if lidar_ok:
            t = threading.Thread(target=self.lidar_thread, daemon=True)
            t.start()
            print("[OK] LIDAR thread started")
        else:
            print("[WARNING] LIDAR not available - using RealSense-only mode")

        if realsense_ok:
            t = threading.Thread(target=self.realsense_thread, daemon=True)
            t.start()
            print("[OK] RealSense thread started")

        print("\n[OK] Proximity bridge operational - PRODUCTION MODE")
        if realsense_ok and lidar_ok:
            print("  • PRIMARY: RealSense (forward 135° arc)")
            print("  • SECONDARY: LiDAR (side/rear, best effort)")
        elif realsense_ok:
            print("  • PRIMARY: RealSense only (forward 135° arc)")
            print("  • LIDAR: Not available (limited side/rear coverage)")
        else:
            print("  • PRIMARY: LiDAR only (360° coverage)")
            print("  • RealSense: Not available (forward arc limited)")
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

            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass

            # FIX BUG #8/#15: Restore stderr and close devnull handle on shutdown
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
