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
        """Connect to RealSense camera"""
        try:
            if not REALSENSE_AVAILABLE:
                print("✗ RealSense library not available")
                return False

            print("Connecting to RealSense for image capture")
            self.pipeline = rs.pipeline()
            config = rs.config()

            # FIX BUG #10: Try multiple configurations with fallbacks
            configs_to_try = [
                # High-res color for crop images (preferred)
                (rs.stream.color, 1280, 720, rs.format.bgr8, 30),
                # Fallback resolutions
                (rs.stream.color, 640, 480, rs.format.bgr8, 30),
                (rs.stream.color, 848, 480, rs.format.bgr8, 30),
                (rs.stream.color, 640, 480, rs.format.bgr8, 15),
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
            self.pipeline = None
            return False

        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
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
