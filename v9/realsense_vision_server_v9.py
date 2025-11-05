#!/usr/bin/env python3
"""
Project Astra NZ - RealSense Vision Server V9
Component 196 - Single owner of RealSense camera
Provides RGB and depth streams to all other components
"""

import sys
import os
import time
import json
import threading
import signal
from datetime import datetime

# Platform-specific imports
try:
    import fcntl
    FCNTL_AVAILABLE = True
except ImportError:
    FCNTL_AVAILABLE = False
    print("[WARNING] fcntl not available (Windows). Process locking will use file-based method.")

try:
    import pyrealsense2 as rs
    import numpy as np
    import cv2
    REALSENSE_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] Required libraries not available: {e}")
    print("Install: pip install pyrealsense2 opencv-python numpy")
    sys.exit(1)

# Configuration
COMPONENT_ID = 196
OUTPUT_DIR = "/tmp/vision_v9"
LOCK_FILE = os.path.join(OUTPUT_DIR, ".lock")
STATUS_FILE = os.path.join(OUTPUT_DIR, "status.json")
LOG_FILE = os.path.join(OUTPUT_DIR, "vision_server.log")

# Stream configuration (can be loaded from config file)
RGB_WIDTH = 640
RGB_HEIGHT = 480
RGB_FPS = 15
DEPTH_WIDTH = 424
DEPTH_HEIGHT = 240
DEPTH_FPS = 15

# Infrared stream (mono) - enable single IR stream
IR_WIDTH = 640
IR_HEIGHT = 480
IR_FPS = 15

# Exposure control
EXPOSURE_US = 6000.0
GAIN = 32.0
TARGET_BRIGHTNESS_LOW = 35
TARGET_BRIGHTNESS_HIGH = 75


class ProcessLock:
    """Ensure only one instance of Vision Server runs."""
    
    def __init__(self, lockfile):
        self.lockfile = lockfile
        self.lock_fd = None
    
    def acquire(self):
        """Try to acquire exclusive lock."""
        try:
            os.makedirs(os.path.dirname(self.lockfile), exist_ok=True)
            
            if FCNTL_AVAILABLE:
                # Unix: Use fcntl for proper locking
                self.lock_fd = open(self.lockfile, 'w')
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lock_fd.write(str(os.getpid()))
                self.lock_fd.flush()
                return True
            else:
                # Windows: Use file-based locking
                if os.path.exists(self.lockfile):
                    try:
                        with open(self.lockfile, 'r') as f:
                            existing_pid = int(f.read().strip())
                        # Check if process is still running
                        try:
                            import psutil
                            if psutil.pid_exists(existing_pid):
                                print(f"[ERROR] Another Vision Server is already running (PID: {existing_pid})")
                                return False
                        except ImportError:
                            # psutil not available, check file age
                            age = time.time() - os.path.getmtime(self.lockfile)
                            if age < 10:  # Lock file less than 10 seconds old
                                print(f"[ERROR] Another Vision Server may be running (PID: {existing_pid})")
                                print("[HINT] If not running, delete: " + self.lockfile)
                                return False
                    except:
                        # Stale lock file, remove it
                        os.remove(self.lockfile)
                
                # Create lock file
                with open(self.lockfile, 'w') as f:
                    f.write(str(os.getpid()))
                return True
                
        except BlockingIOError:
            # Another instance is running (Unix)
            try:
                with open(self.lockfile, 'r') as f:
                    existing_pid = f.read().strip()
                print(f"[ERROR] Another Vision Server is already running (PID: {existing_pid})")
            except:
                print("[ERROR] Another Vision Server is already running")
            return False
        except Exception as e:
            print(f"[ERROR] Lock acquisition failed: {e}")
            return False
    
    def release(self):
        """Release lock."""
        if self.lock_fd:
            try:
                if FCNTL_AVAILABLE:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
            except:
                pass
        try:
            os.remove(self.lockfile)
        except:
            pass


class VisionServer:
    def __init__(self):
        self.pipeline = None
        self.rgb_sensor = None
        self.running = True
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'start_time': time.time(),
            'rgb_frames': 0,
            'depth_frames': 0,
            'ir_frames': 0,
            'errors': 0,
            'last_error': None,
            'last_error_time': None
        }
        
        # Frame tracking
        self.frame_number = 0
        
        # Exposure control
        self.exposure_us = EXPOSURE_US
        self.gain_value = GAIN
        self.last_exposure_update = 0.0
        
        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Setup logging
        self.log_file = open(LOG_FILE, 'a')
        self.log(f"Vision Server V9 starting - PID: {os.getpid()}")
    
    def log(self, message):
        """Log message to file and stdout."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        print(message)
        try:
            self.log_file.write(log_line)
            self.log_file.flush()
        except:
            pass
    
    def adjust_rgb_exposure(self, mean_brightness):
        """Adaptive exposure control."""
        if self.rgb_sensor is None:
            return
        
        now = time.time()
        if now - self.last_exposure_update < 0.4:  # Limit update rate
            return
        
        try:
            if mean_brightness > TARGET_BRIGHTNESS_HIGH:
                # Too bright → reduce exposure
                if self.rgb_sensor.supports(rs.option.exposure):
                    self.exposure_us = max(500.0, self.exposure_us - 500.0)
                    self.rgb_sensor.set_option(rs.option.exposure, float(self.exposure_us))
                if self.rgb_sensor.supports(rs.option.gain):
                    self.gain_value = max(8.0, self.gain_value - 2.0)
                    self.rgb_sensor.set_option(rs.option.gain, float(self.gain_value))
            elif mean_brightness < TARGET_BRIGHTNESS_LOW:
                # Too dark → increase exposure
                if self.rgb_sensor.supports(rs.option.exposure):
                    self.exposure_us = min(20000.0, self.exposure_us + 500.0)
                    self.rgb_sensor.set_option(rs.option.exposure, float(self.exposure_us))
                if self.rgb_sensor.supports(rs.option.gain):
                    self.gain_value = min(64.0, self.gain_value + 2.0)
                    self.rgb_sensor.set_option(rs.option.gain, float(self.gain_value))
            
            self.last_exposure_update = now
        except Exception as e:
            pass  # Ignore exposure control errors
    
    def configure_camera(self, profile):
        """Configure camera settings."""
        try:
            device = profile.get_device()
            sensors = device.query_sensors()
            
            for sensor in sensors:
                try:
                    name = sensor.get_info(rs.camera_info.name) if hasattr(rs, 'camera_info') else ''
                except:
                    name = ''
                
                # Configure RGB sensor
                if 'rgb' in name.lower() or True:  # Apply to any sensor that supports it
                    if hasattr(sensor, 'supports'):
                        try:
                            # Manual exposure mode
                            if sensor.supports(rs.option.enable_auto_exposure):
                                sensor.set_option(rs.option.enable_auto_exposure, 0)
                            
                            if sensor.supports(rs.option.exposure):
                                sensor.set_option(rs.option.exposure, float(self.exposure_us))
                            
                            if sensor.supports(rs.option.gain):
                                sensor.set_option(rs.option.gain, float(self.gain_value))
                            
                            if sensor.supports(rs.option.auto_exposure_priority):
                                sensor.set_option(rs.option.auto_exposure_priority, 0.0)
                            
                            if sensor.supports(rs.option.backlight_compensation):
                                sensor.set_option(rs.option.backlight_compensation, 1.0)
                            
                            self.rgb_sensor = sensor
                            self.log(f"✓ RGB sensor configured (exposure: {self.exposure_us}us, gain: {self.gain_value})")
                            break
                        except Exception as e:
                            continue
        except Exception as e:
            self.log(f"⚠ Camera configuration warning: {e}")
    
    def connect_camera(self):
        """Initialize RealSense camera."""
        self.log("Connecting to RealSense camera...")
        
        try:
            self.pipeline = rs.pipeline()
            config = rs.config()
            
            # Enable RGB stream
            config.enable_stream(rs.stream.color, RGB_WIDTH, RGB_HEIGHT, rs.format.bgr8, RGB_FPS)
            
            # Enable depth stream
            config.enable_stream(rs.stream.depth, DEPTH_WIDTH, DEPTH_HEIGHT, rs.format.z16, DEPTH_FPS)

            # Enable infrared stream (mono)
            try:
                # Some devices expose two IR streams; enabling index 1 is usually IR Left
                config.enable_stream(rs.stream.infrared, IR_WIDTH, IR_HEIGHT, rs.format.y8, IR_FPS)
            except Exception:
                # Fallback: try specifying stream index 1 explicitly
                try:
                    config.enable_stream(rs.stream.infrared, 1, IR_WIDTH, IR_HEIGHT, rs.format.y8, IR_FPS)
                except Exception:
                    # If IR not available, continue without it
                    pass
            
            # Start pipeline
            profile = self.pipeline.start(config)
            
            # Configure camera settings
            self.configure_camera(profile)
            
            # Stabilization period
            self.log("Camera stabilizing...")
            time.sleep(2)
            
            # Test frame capture
            for attempt in range(10):
                try:
                    frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                    if frames.get_color_frame() and frames.get_depth_frame():
                        self.log(f"✓ Camera connected - RGB: {RGB_WIDTH}x{RGB_HEIGHT}@{RGB_FPS}fps, Depth: {DEPTH_WIDTH}x{DEPTH_HEIGHT}@{DEPTH_FPS}fps")
                        return True
                except:
                    if attempt < 9:
                        time.sleep(0.5)
                        continue
            
            raise RuntimeError("Failed to capture test frames")
            
        except Exception as e:
            self.log(f"✗ Camera connection failed: {e}")
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
                self.pipeline = None
            return False
    
    def write_rgb_frame(self, color_image):
        """Write RGB frame with metadata."""
        try:
            self.frame_number += 1
            timestamp = time.time()
            
            # Calculate brightness for exposure control
            try:
                gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
                mean_brightness = float(np.mean(gray))
                self.adjust_rgb_exposure(mean_brightness)
            except:
                mean_brightness = 0
            
            # Write image atomically
            rgb_tmp = os.path.join(OUTPUT_DIR, "rgb_latest.jpg.tmp")
            rgb_path = os.path.join(OUTPUT_DIR, "rgb_latest.jpg")
            
            cv2.imwrite(rgb_tmp, color_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            os.replace(rgb_tmp, rgb_path)
            
            # Write metadata
            meta_tmp = os.path.join(OUTPUT_DIR, "rgb_latest.json.tmp")
            meta_path = os.path.join(OUTPUT_DIR, "rgb_latest.json")
            
            metadata = {
                'frame_number': self.frame_number,
                'timestamp': timestamp,
                'timestamp_iso': datetime.fromtimestamp(timestamp).isoformat(),
                'width': RGB_WIDTH,
                'height': RGB_HEIGHT,
                'fps_target': RGB_FPS,
                'exposure_us': self.exposure_us,
                'gain': self.gain_value,
                'brightness_mean': mean_brightness,
                'quality': 85
            }
            
            with open(meta_tmp, 'w') as f:
                json.dump(metadata, f)
            os.replace(meta_tmp, meta_path)
            
            self.stats['rgb_frames'] += 1
            return True
            
        except Exception as e:
            self.log(f"✗ RGB write error: {e}")
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            self.stats['last_error_time'] = time.time()
            return False
    
    def write_depth_frame(self, depth_frame):
        """Write depth frame with metadata."""
        try:
            timestamp = time.time()
            
            # Get depth data as numpy array
            depth_image = np.asanyarray(depth_frame.get_data())
            
            # Write binary depth data atomically
            depth_tmp = os.path.join(OUTPUT_DIR, "depth_latest.bin.tmp")
            depth_path = os.path.join(OUTPUT_DIR, "depth_latest.bin")
            
            depth_image.tofile(depth_tmp)
            os.replace(depth_tmp, depth_path)

            # Also write a pseudo-color JPEG for easy streaming
            try:
                # Normalize to 8-bit (invert so nearer = brighter)
                d_clip = np.clip(depth_image.astype(np.float32), 0, 5000)
                d_norm = (d_clip / 5000.0) * 255.0
                d8 = d_norm.astype(np.uint8)
                d8 = 255 - d8
                depth_color = cv2.applyColorMap(d8, getattr(cv2, 'COLORMAP_TURBO', cv2.COLORMAP_JET))
                dj_tmp = os.path.join(OUTPUT_DIR, "depth_latest.jpg.tmp")
                dj_path = os.path.join(OUTPUT_DIR, "depth_latest.jpg")
                cv2.imwrite(dj_tmp, depth_color, [cv2.IMWRITE_JPEG_QUALITY, 85])
                os.replace(dj_tmp, dj_path)
            except Exception:
                pass
            
            # Write metadata
            meta_tmp = os.path.join(OUTPUT_DIR, "depth_latest.json.tmp")
            meta_path = os.path.join(OUTPUT_DIR, "depth_latest.json")
            
            metadata = {
                'frame_number': self.frame_number,
                'timestamp': timestamp,
                'timestamp_iso': datetime.fromtimestamp(timestamp).isoformat(),
                'width': DEPTH_WIDTH,
                'height': DEPTH_HEIGHT,
                'fps_target': DEPTH_FPS,
                'depth_scale': 0.001,
                'min_distance_m': 0.2,
                'max_distance_m': 25.0,
                'data_type': 'uint16',
                'file_size_bytes': depth_image.nbytes
            }
            
            with open(meta_tmp, 'w') as f:
                json.dump(metadata, f)
            os.replace(meta_tmp, meta_path)
            
            self.stats['depth_frames'] += 1
            return True
            
        except Exception as e:
            self.log(f"✗ Depth write error: {e}")
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            self.stats['last_error_time'] = time.time()
            return False

    def write_ir_frame(self, ir_frame):
        """Write infrared (mono) frame to JPEG with metadata."""
        try:
            timestamp = time.time()
            ir_image = np.asanyarray(ir_frame.get_data())  # expected Y8
            # Ensure 2D mono
            if ir_image.ndim == 3 and ir_image.shape[2] == 1:
                ir_image = ir_image[:, :, 0]
            ir_tmp = os.path.join(OUTPUT_DIR, "ir_latest.jpg.tmp")
            ir_path = os.path.join(OUTPUT_DIR, "ir_latest.jpg")
            cv2.imwrite(ir_tmp, ir_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            os.replace(ir_tmp, ir_path)

            meta_tmp = os.path.join(OUTPUT_DIR, "ir_latest.json.tmp")
            meta_path = os.path.join(OUTPUT_DIR, "ir_latest.json")
            metadata = {
                'frame_number': self.frame_number,
                'timestamp': timestamp,
                'timestamp_iso': datetime.fromtimestamp(timestamp).isoformat(),
                'width': int(ir_image.shape[1]),
                'height': int(ir_image.shape[0]),
                'fps_target': IR_FPS,
            }
            with open(meta_tmp, 'w') as f:
                json.dump(metadata, f)
            os.replace(meta_tmp, meta_path)

            self.stats['ir_frames'] += 1
            return True
        except Exception as e:
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            self.stats['last_error_time'] = time.time()
            return False
    
    def update_status(self):
        """Write health status file."""
        try:
            uptime = time.time() - self.stats['start_time']
            rgb_fps = self.stats['rgb_frames'] / uptime if uptime > 0 else 0
            depth_fps = self.stats['depth_frames'] / uptime if uptime > 0 else 0
            ir_fps = self.stats['ir_frames'] / uptime if uptime > 0 else 0
            
            status = {
                'component_id': COMPONENT_ID,
                'component_name': 'RealSense Vision Server V9',
                'status': 'RUNNING',
                'uptime_seconds': int(uptime),
                'frames_processed': {
                    'rgb': self.stats['rgb_frames'],
                    'depth': self.stats['depth_frames'],
                    'ir': self.stats['ir_frames']
                },
                'fps': {
                    'rgb_actual': round(rgb_fps, 1),
                    'depth_actual': round(depth_fps, 1),
                    'ir_actual': round(ir_fps, 1),
                    'rgb_target': RGB_FPS,
                    'depth_target': DEPTH_FPS,
                    'ir_target': IR_FPS
                },
                'errors': {
                    'count': self.stats['errors'],
                    'last_error': self.stats['last_error'],
                    'last_error_time': self.stats['last_error_time']
                },
                'timestamp': time.time(),
                'pid': os.getpid()
            }
            
            status_tmp = STATUS_FILE + ".tmp"
            with open(status_tmp, 'w') as f:
                json.dump(status, f, indent=2)
            os.replace(status_tmp, STATUS_FILE)
            
        except Exception as e:
            pass  # Don't fail on status write errors
    
    def capture_loop(self):
        """Main capture loop."""
        self.log("✓ Vision Server operational")
        self.log(f"  • RGB: {RGB_WIDTH}x{RGB_HEIGHT} @ {RGB_FPS} FPS")
        self.log(f"  • Depth: {DEPTH_WIDTH}x{DEPTH_HEIGHT} @ {DEPTH_FPS} FPS")
        self.log(f"  • Output: {OUTPUT_DIR}")
        self.log("")
        
        last_status_update = time.time()
        consecutive_errors = 0
        
        while self.running:
            try:
                # Wait for frames
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                
                # Get color, depth, and infrared frames
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                try:
                    ir_frame = frames.get_infrared_frame()
                except Exception:
                    # Some devices require index parameter
                    try:
                        ir_frame = frames.get_infrared_frame(1)
                    except Exception:
                        ir_frame = None
                
                if not color_frame or not depth_frame:
                    consecutive_errors += 1
                    if consecutive_errors > 10:
                        self.log("⚠ Too many frame capture failures")
                        consecutive_errors = 0
                    time.sleep(0.01)
                    continue
                
                # Reset error counter
                consecutive_errors = 0
                
                # Convert color frame to numpy array
                color_image = np.asanyarray(color_frame.get_data())
                
                # Write frames
                self.write_rgb_frame(color_image)
                self.write_depth_frame(depth_frame)
                if ir_frame is not None:
                    self.write_ir_frame(ir_frame)
                
                # Update status periodically
                if time.time() - last_status_update > 1.0:
                    self.update_status()
                    last_status_update = time.time()
                
                # Small delay to maintain target FPS
                time.sleep(0.001)
                
            except Exception as e:
                self.log(f"✗ Capture loop error: {e}")
                consecutive_errors += 1
                
                if consecutive_errors > 50:
                    self.log("✗ Too many errors, attempting camera restart...")
                    try:
                        self.pipeline.stop()
                        time.sleep(2)
                        if not self.connect_camera():
                            self.log("✗ Camera restart failed, exiting")
                            break
                        consecutive_errors = 0
                    except:
                        break
                
                time.sleep(0.1)
    
    def shutdown(self):
        """Clean shutdown."""
        self.log("Shutting down Vision Server...")
        self.running = False
        
        if self.pipeline:
            try:
                self.pipeline.stop()
            except:
                pass
        
        # Write final status
        try:
            status = {
                'component_id': COMPONENT_ID,
                'status': 'STOPPED',
                'timestamp': time.time()
            }
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f)
        except:
            pass
        
        if self.log_file:
            self.log_file.close()
        
        self.log("✓ Vision Server stopped cleanly")
    
    def run(self):
        """Main execution."""
        print("=" * 60)
        print("PROJECT ASTRA NZ - VISION SERVER V9")
        print("=" * 60)
        print(f"Component ID: {COMPONENT_ID}")
        print(f"Output Directory: {OUTPUT_DIR}")
        print("=" * 60)
        
        # Connect to camera
        if not self.connect_camera():
            self.log("✗ Failed to connect to camera")
            return False
        
        # Start capture loop
        try:
            self.capture_loop()
        except KeyboardInterrupt:
            self.log("\n⚠ Keyboard interrupt received")
        except Exception as e:
            self.log(f"✗ Unexpected error: {e}")
        finally:
            self.shutdown()
        
        return True


def main():
    """Main entry point."""
    # Check for lock
    lock = ProcessLock(LOCK_FILE)
    if not lock.acquire():
        print("\n[SOLUTION] If the other instance is not running:")
        print(f"  rm {LOCK_FILE}")
        print(f"  ps aux | grep realsense_vision_server")
        sys.exit(1)
    
    # Setup signal handlers
    server = VisionServer()
    
    def signal_handler(sig, frame):
        print("\n⚠ Signal received, shutting down...")
        server.shutdown()
        lock.release()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        success = server.run()
        sys.exit(0 if success else 1)
    finally:
        lock.release()


if __name__ == "__main__":
    main()

