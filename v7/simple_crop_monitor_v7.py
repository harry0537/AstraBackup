#!/usr/bin/env python3
"""
Project Astra NZ - Simple Crop Monitor V7
Captures one image per minute with RealSense for AWS relay
Component 198 - Image capture only - Clean Version
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
CAPTURE_INTERVAL = 60  # 1 minute
IMAGE_OUTPUT = "/tmp/crop_latest.jpg"
STATUS_FILE = "/tmp/crop_monitor_v7.json"

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
            
            # High-res color for crop images
            config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
            
            self.pipeline.start(config)
            
            # Warm-up
            for _ in range(10):
                self.pipeline.wait_for_frames(timeout_ms=1000)
                
            print("✓ RealSense connected")
            return True
            
        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            return False
            
    def capture_image(self):
        """Capture and save single image"""
        if not self.pipeline:
            return False
            
        try:
            # Capture frame
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            color_frame = frames.get_color_frame()
            
            if not color_frame:
                return False
                
            # Convert to numpy array
            image = np.asanyarray(color_frame.get_data())
            
            # Save image
            cv2.imwrite(IMAGE_OUTPUT, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Update status
            self.capture_count += 1
            self.last_capture_time = time.time()
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'capture_count': self.capture_count,
                'image_path': IMAGE_OUTPUT,
                'image_size': os.path.getsize(IMAGE_OUTPUT) if os.path.exists(IMAGE_OUTPUT) else 0
            }
            
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f)
            
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Captured image #{self.capture_count}", end='')
            return True
            
        except Exception as e:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Capture failed: {e}", end='')
            return False
            
    def run(self):
        """Main execution loop"""
        print("=" * 60)
        print("Simple Crop Monitor V7 - Component 198")
        print("=" * 60)
        print(f"Capture interval: {CAPTURE_INTERVAL} seconds")
        print(f"Output: {IMAGE_OUTPUT}")
        print("=" * 60)
        
        if not self.connect_camera():
            print("✗ Cannot operate without camera")
            return
            
        print("\n✓ Crop monitor operational")
        print("  • Capturing 1 image per minute")
        print("  • Images saved to /tmp for relay")
        print()
        
        # Initial capture
        self.capture_image()
        
        try:
            while self.running:
                current_time = time.time()
                
                # Check if it's time for next capture
                if current_time - self.last_capture_time >= CAPTURE_INTERVAL:
                    self.capture_image()
                    
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
