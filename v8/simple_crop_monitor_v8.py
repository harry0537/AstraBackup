#!/usr/bin/env python3
"""
Project Astra NZ - Simple Crop Monitor V8
Uses images from Proximity Bridge - No camera conflict
Component 198 - Image archive with rolling dashboard buffer
"""

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except Exception as e:
    CV2_AVAILABLE = False
    print(f"[ERROR] OpenCV not available: {e}")
import time
import os
import glob
from datetime import datetime
import json

# Configuration
COMPONENT_ID = 198
CAPTURE_INTERVAL = 5  # 5 seconds
MAX_IMAGES = 10  # Maximum number of archived images
IMAGE_DIR = "/tmp/crop_archive"  # Directory for archived images
DASHBOARD_DIR = "/tmp/rover_vision"  # Directory for dashboard rolling images (1-10)
STATUS_FILE = "/tmp/crop_monitor_v8.json"
SOURCE_IMAGE = "/tmp/realsense_latest.jpg"  # Image from proximity bridge

# Create directories if they don't exist
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)

class SimpleCropMonitor:
    def __init__(self):
        self.running = True
        self.capture_count = 0
        self.last_capture_time = 0
        self.current_slot = 1  # Rolling slot number 1-10

    def check_source_available(self):
        """Wait for proximity bridge to start providing images"""
        print("Waiting for Proximity Bridge to start providing images...")
        
        for i in range(20):
            if os.path.exists(SOURCE_IMAGE):
                print(f"✓ Found image source from Proximity Bridge")
                return True
            time.sleep(1)
            if i % 5 == 0:
                print(f"  Still waiting... ({i}/20 seconds)")
        
        print(f"✗ Proximity Bridge not providing images after 20 seconds")
        print(f"   Make sure Proximity Bridge (Component 195) is running first!")
        return False

    def manage_image_archive(self):
        """Manage rolling archive - delete oldest if over limit"""
        try:
            images = sorted(glob.glob(os.path.join(IMAGE_DIR, "crop_*.jpg")), 
                          key=os.path.getmtime)
            
            while len(images) >= MAX_IMAGES:
                oldest = images.pop(0)
                try:
                    os.remove(oldest)
                except Exception as e:
                    print(f"\n  [ARCHIVE] Failed to delete {oldest}: {e}")
                    break
        except Exception as e:
            print(f"\n  [ARCHIVE] Archive management failed: {e}")

    def capture_image(self):
        """Copy image from proximity bridge to archive and dashboard slots"""
        if not os.path.exists(SOURCE_IMAGE):
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Source image not available", end='')
            return False
        if not CV2_AVAILABLE:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ OpenCV not installed", end='')
            return False

        try:
            # Read image from proximity bridge robustly to avoid partial reads
            # when the producer replaces the file while we're reading it.
            try:
                with open(SOURCE_IMAGE, 'rb') as f:
                    data = f.read()
                npbuf = np.frombuffer(data, dtype=np.uint8)
                image = cv2.imdecode(npbuf, cv2.IMREAD_COLOR)
            except Exception:
                image = cv2.imread(SOURCE_IMAGE)
            if image is None or image.size == 0:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Invalid image data", end='')
                return False

            # 1. Save to archive with timestamp
            self.manage_image_archive()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_path = os.path.join(IMAGE_DIR, f"crop_{timestamp}.jpg")
            ok_archive = cv2.imwrite(archive_path, image, [cv2.IMWRITE_JPEG_QUALITY, 70])

            # 2. Save to dashboard rolling buffer (1-10)
            dashboard_path = os.path.join(DASHBOARD_DIR, f"{self.current_slot}.jpg")
            ok_dash = cv2.imwrite(dashboard_path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])

            if not ok_archive or not ok_dash:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Failed to save image(s)", end='')
                return False
            
            # Update status
            self.capture_count += 1
            self.last_capture_time = time.time()
            num_archived = len(glob.glob(os.path.join(IMAGE_DIR, "crop_*.jpg")))
            
            # Advance to next slot (1-10 rolling)
            next_slot = self.current_slot
            self.current_slot = (self.current_slot % 10) + 1
            
            # Debug output
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Image #{self.capture_count} → slot {next_slot} (archive: {num_archived}/{MAX_IMAGES})", end='')

            # Write status file
            # Compute sizes safely
            try:
                archive_size = os.path.getsize(archive_path)
            except Exception:
                archive_size = 0

            status = {
                'timestamp': datetime.now().isoformat(),
                'capture_count': self.capture_count,
                'latest_image': archive_path,
                'image_size': archive_size,
                'total_archived': num_archived,
                'archive_dir': IMAGE_DIR,
                'latest_image_timestamp': time.time(),
                'current_slot': self.current_slot
            }

            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status, f)
            except Exception as e:
                print(f"\n  [STATUS] Failed to write status file: {e}")

            return True

        except Exception as e:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Capture failed: {e}", end='')
            return False

    def run(self):
        """Main execution loop"""
        print("=" * 60)
        print("Simple Crop Monitor V8 - Component 198")
        print("=" * 60)
        print(f"Source: Proximity Bridge ({SOURCE_IMAGE})")
        print(f"Capture interval: {CAPTURE_INTERVAL} seconds")
        print(f"Archive directory: {IMAGE_DIR}")
        print(f"Dashboard slots: {DASHBOARD_DIR} (1-10)")
        print(f"Max archived images: {MAX_IMAGES}")
        print("=" * 60)

        if not self.check_source_available():
            print("✗ Image source not available yet - will keep waiting and retrying...")
            # Keep waiting until source appears instead of exiting
            while not os.path.exists(SOURCE_IMAGE):
                time.sleep(1)
            print("✓ Source image detected, continuing...")

        print("\n✓ Crop monitor operational")
        print(f"  • Using images from Proximity Bridge")
        print(f"  • Capturing 1 image every {CAPTURE_INTERVAL} seconds")
        print(f"  • Rolling archive of {MAX_IMAGES} images")
        print(f"  • Dashboard buffer: 10 slots")
        print()

        # Initialize all 10 dashboard slots
        print("Initializing dashboard slots (1-10)...")
        for i in range(10):
            success = self.capture_image()
            if success:
                print(f"  • Initialized slot {i+1}/10 ✓")
            else:
                print(f"  • Failed to initialize slot {i+1}/10 ✗")
            time.sleep(0.3)
        print("✓ All dashboard slots initialized\n")
        
        # Reset to slot 1 for normal operation
        self.current_slot = 1

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
                        if consecutive_failures >= max_failures:
                            print(f"\n⚠ Too many consecutive failures ({max_failures})")
                            print(f"  Proximity bridge may have stopped")
                            # Keep trying but don't exit
                            consecutive_failures = 0

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n✓ Crop monitor stopped by user")
        except Exception as e:
            print(f"\n✗ Error in main loop: {e}")
        finally:
            self.running = False

if __name__ == '__main__':
    monitor = SimpleCropMonitor()
    monitor.run()

