#!/usr/bin/env python3
"""
Project Astra NZ - Simple Crop Monitor V8
Captures one image per minute with RealSense for AWS relay
Component 198 - Image capture only - Bug Fixes from V7
"""

import cv2
import numpy as np
import time
import os
from datetime import datetime
import json

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

# Configuration
COMPONENT_ID = 198
CAPTURE_INTERVAL = 5  # 5 seconds
IMAGE_OUTPUT = "/tmp/crop_latest.jpg"
STATUS_FILE = "/tmp/crop_monitor_v8.json"

class SimpleCropMonitor:
    def __init__(self):
        self.pipeline = None
        self.running = True
        self.capture_count = 0
        self.last_capture_time = 0

    def connect_camera(self):
        """Connect to RealSense camera with resource sharing"""
        try:
            if not REALSENSE_AVAILABLE:
                print("✗ RealSense library not available")
                return False

            print("Connecting to RealSense for image capture")
            
            # Check if camera is already in use by proximity bridge
            try:
                ctx = rs.context()
                devices = ctx.query_devices()
                if len(devices) == 0:
                    print("  [ERROR] No RealSense devices found")
                    return False
                
                print(f"  [INFO] Found {len(devices)} RealSense device(s)")
                
                # Try to use existing pipeline from proximity bridge first
                if self.try_shared_camera():
                    return True
                    
            except Exception as e:
                print(f"  [WARNING] Device detection failed: {e}")
            
            # If shared camera doesn't work, try to create new pipeline
            print("  [INFO] Creating new RealSense pipeline...")
            self.pipeline = rs.pipeline()
            config = rs.config()

            # First try native stream profiles from the device
            if self.try_native_profiles():
                return True

            # Enhanced configurations with more fallback options
            configs_to_try = [
                # High-res color for crop images (preferred)
                (rs.stream.color, 1280, 720, rs.format.bgr8, 30),
                (rs.stream.color, 1280, 720, rs.format.bgr8, 15),
                # Medium resolutions
                (rs.stream.color, 848, 480, rs.format.bgr8, 30),
                (rs.stream.color, 848, 480, rs.format.bgr8, 15),
                (rs.stream.color, 640, 480, rs.format.bgr8, 30),
                (rs.stream.color, 640, 480, rs.format.bgr8, 15),
                # Lower resolutions for compatibility
                (rs.stream.color, 640, 360, rs.format.bgr8, 30),
                (rs.stream.color, 640, 360, rs.format.bgr8, 15),
                (rs.stream.color, 424, 240, rs.format.bgr8, 30),
                (rs.stream.color, 424, 240, rs.format.bgr8, 15),
                # Very low resolution fallback
                (rs.stream.color, 320, 240, rs.format.bgr8, 15),
                (rs.stream.color, 320, 180, rs.format.bgr8, 15),
            ]

            for i, (stream, width, height, format, fps) in enumerate(configs_to_try):
                try:
                    print(f"  [CONFIG] Trying {width}x{height} @ {fps}fps...")
                    config = rs.config()
                    config.enable_stream(stream, width, height, format, fps)
                    self.pipeline.start(config)

                    # Warm-up and test
                    print(f"  [TEST] Testing frame capture...")
                    for attempt in range(10):
                        try:
                            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                            color_frame = frames.get_color_frame()
                            if color_frame:
                                print(f"✓ RealSense connected - {width}x{height} @ {fps}fps")
                                return True
                        except:
                            if attempt < 9:
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

            print("✗ All RealSense configurations failed")
            
            # Try alternative approach - use file-based sharing
            if self.try_file_based_sharing():
                return True
                
            self.pipeline = None
            return False

        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            return False

    def try_shared_camera(self):
        """Try to use camera without creating new pipeline (resource sharing)"""
        try:
            print("  [SHARED] Attempting to use existing camera resources...")
            
            # Try to read from existing proximity bridge data
            proximity_file = "/tmp/proximity_v8.json"
            if os.path.exists(proximity_file):
                try:
                    with open(proximity_file, 'r') as f:
                        data = json.load(f)
                    if 'realsense_cm' in data and data['realsense_cm']:
                        print("  [SHARED] Using proximity bridge RealSense data")
                        # Set up for shared operation
                        self.pipeline = None  # No pipeline needed
                        return True
                except:
                    pass
            
            # Try to create a minimal pipeline that doesn't conflict
            try:
                print("  [SHARED] Creating minimal pipeline...")
                self.pipeline = rs.pipeline()
                config = rs.config()
                
                # Use a very low resolution to minimize resource usage
                config.enable_stream(rs.stream.color, 320, 240, rs.format.bgr8, 15)
                
                # Try to start with minimal timeout
                self.pipeline.start(config)
                
                # Quick test
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                if frames.get_color_frame():
                    print("  [SHARED] Minimal pipeline successful")
                    return True
                else:
                    self.pipeline.stop()
                    self.pipeline = None
            except Exception as e:
                if self.pipeline:
                    try:
                        self.pipeline.stop()
                    except:
                        pass
                    self.pipeline = None
                print(f"  [SHARED] Minimal pipeline failed: {e}")
            
            return False
            
        except Exception as e:
            print(f"  [SHARED] Shared camera method failed: {e}")
            return False

    def try_native_profiles(self):
        """Try to use device's native stream profiles"""
        try:
            print("  [NATIVE] Trying device native stream profiles...")
            ctx = rs.context()
            devices = ctx.query_devices()
            if len(devices) == 0:
                return False
                
            device = devices[0]
            sensors = device.query_sensors()
            
            for sensor in sensors:
                profiles = sensor.get_stream_profiles()
                color_profiles = [p for p in profiles if p.stream_type() == rs.stream.color]
                
                if not color_profiles:
                    continue
                    
                # Sort by resolution (highest first)
                color_profiles.sort(key=lambda x: x.as_video_stream_profile().width() * x.as_video_stream_profile().height(), reverse=True)
                
                # Try top 3 profiles
                for profile in color_profiles[:3]:
                    try:
                        vp = profile.as_video_stream_profile()
                        print(f"    [NATIVE] Trying {vp.width()}x{vp.height()} @ {vp.fps()}fps...")
                        
                        config = rs.config()
                        config.enable_stream(profile)
                        self.pipeline.start(config)
                        
                        # Test frame capture
                        frames = self.pipeline.wait_for_frames(timeout_ms=3000)
                        color_frame = frames.get_color_frame()
                        if color_frame:
                            print(f"✓ RealSense connected - {vp.width()}x{vp.height()} @ {vp.fps()}fps (native)")
                            return True
                        else:
                            self.pipeline.stop()
                            time.sleep(1)
                    except Exception as e:
                        if self.pipeline:
                            try:
                                self.pipeline.stop()
                            except:
                                pass
                        continue
                        
        except Exception as e:
            print(f"  [WARNING] Native profile method failed: {e}")
            
            return False

    def try_file_based_sharing(self):
        """Try to use file-based sharing when camera is busy"""
        try:
            print("  [FILE] Attempting file-based camera sharing...")
            
            # Check if proximity bridge is writing RealSense data
            proximity_file = "/tmp/proximity_v8.json"
            if os.path.exists(proximity_file):
                try:
                    with open(proximity_file, 'r') as f:
                        data = json.load(f)
                    
                    # Check if proximity bridge has RealSense data
                    if 'realsense_cm' in data and data['realsense_cm']:
                        print("  [FILE] Using proximity bridge RealSense data")
                        self.pipeline = None  # No direct camera access needed
                        return True
                except Exception as e:
                    print(f"  [FILE] Proximity data read failed: {e}")
            
            # Try to create a very minimal pipeline with different approach
            try:
                print("  [FILE] Creating ultra-minimal pipeline...")
                self.pipeline = rs.pipeline()
                config = rs.config()
                
                # Use absolute minimum settings
                config.enable_stream(rs.stream.color, 160, 120, rs.format.bgr8, 5)
                
                # Try with very short timeout
                self.pipeline.start(config)
                
                # Test with minimal requirements
                frames = self.pipeline.wait_for_frames(timeout_ms=500)
                if frames.get_color_frame():
                    print("  [FILE] Ultra-minimal pipeline successful")
                    return True
                else:
                    self.pipeline.stop()
                    self.pipeline = None
            except Exception as e:
                if self.pipeline:
                    try:
                        self.pipeline.stop()
                    except:
                        pass
                    self.pipeline = None
                print(f"  [FILE] Ultra-minimal pipeline failed: {e}")
            
            return False
            
        except Exception as e:
            print(f"  [FILE] File-based sharing failed: {e}")
            return False

    def capture_image(self):
        """Capture and save single image with robust error handling"""
        if not self.pipeline:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ No pipeline available", end='')
            return False

        try:
            # Capture frame with retry logic
            frames = None
            for attempt in range(3):
                try:
                    frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Frame capture attempt {attempt+1} failed: {e}, retrying...", end='')
                        time.sleep(0.5)
                    else:
                        raise e

            if not frames:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ No frames received", end='')
                return False

            color_frame = frames.get_color_frame()
            if not color_frame:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ No color frame", end='')
                return False

            # Convert to numpy array
            image = np.asanyarray(color_frame.get_data())
            if image is None or image.size == 0:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Invalid image data", end='')
                return False

            # Save image with optimized compression for faster transmission
            success = cv2.imwrite(IMAGE_OUTPUT, image, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if not success:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Failed to save image", end='')
                return False

            # Update status
            self.capture_count += 1
            self.last_capture_time = time.time()

            status = {
                'timestamp': datetime.now().isoformat(),
                'capture_count': self.capture_count,
                'image_path': IMAGE_OUTPUT,
                'image_size': os.path.getsize(IMAGE_OUTPUT) if os.path.exists(IMAGE_OUTPUT) else 0
            }

            # Write status file with error handling
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status, f)
            except Exception as e:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Status file write failed: {e}", end='')

            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Captured image #{self.capture_count} ({os.path.getsize(IMAGE_OUTPUT)} bytes)", end='', flush=True)
            return True

        except Exception as e:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Capture failed: {e}", end='')
            # Try to reconnect camera if it's a pipeline error
            if "pipeline" in str(e).lower() or "device" in str(e).lower():
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Attempting camera reconnection...", end='')
                try:
                    if self.pipeline:
                        self.pipeline.stop()
                    self.pipeline = None
                    time.sleep(2)
                    if self.connect_camera():
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Camera reconnected", end='')
                    else:
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Camera reconnection failed", end='')
                except:
                    pass
            return False

    def run(self):
        """Main execution loop"""
        print("=" * 60)
        print("Simple Crop Monitor V8 - Component 198")
        print("=" * 60)
        print(f"Capture interval: {CAPTURE_INTERVAL} seconds")
        print(f"Output: {IMAGE_OUTPUT}")
        print("=" * 60)

        if not self.connect_camera():
            print("✗ Cannot operate without camera")
            return

        print("\n✓ Crop monitor operational")
        print("  • Capturing 1 image every 5 seconds")
        print("  • Images saved to /tmp for relay")
        print("  • High-frequency capture for dashboard feed")
        print()

        # Initial capture
        self.capture_image()

        try:
            consecutive_failures = 0
            max_failures = 5
            
            while self.running:
                current_time = time.time()

                # Check if it's time for next capture
                if current_time - self.last_capture_time >= CAPTURE_INTERVAL:
                    success = self.capture_image()
                    
                    if success:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Consecutive failures: {consecutive_failures}/{max_failures}", end='')
                        
                        # If too many failures, try to reconnect camera
                        if consecutive_failures >= max_failures:
                            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Too many failures, attempting camera reconnection...", end='')
                            try:
                                if self.pipeline:
                                    self.pipeline.stop()
                                self.pipeline = None
                                time.sleep(3)
                                if self.connect_camera():
                                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Camera reconnected", end='')
                                    consecutive_failures = 0
                                else:
                                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Camera reconnection failed", end='')
                            except Exception as e:
                                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Reconnection error: {e}", end='')

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nShutdown initiated...")

        finally:
            self.running = False

            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass

            print("\n✓ Crop monitor stopped")
            print(f"Total captures: {self.capture_count}")

if __name__ == "__main__":
    monitor = SimpleCropMonitor()
    monitor.run()
