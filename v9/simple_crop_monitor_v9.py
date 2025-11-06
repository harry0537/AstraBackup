#!/usr/bin/env python3
"""
Project Astra NZ - Simple Crop Monitor V9
Reads images from Vision Server - No camera conflict
Component 198 - Modified for V9 Architecture
"""

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except Exception as e:
    CV2_AVAILABLE = False
    print(f"[ERROR] OpenCV not available: {e}")
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
import time
import os
import glob
from datetime import datetime
import json

# Configuration
COMPONENT_ID = 198
CAPTURE_INTERVAL = 10  # 10 seconds (changed from 5 in V8)
MAX_IMAGES = 10  # Maximum number of archived images
IMAGE_DIR = "/tmp/crop_archive"  # Directory for archived images
DASHBOARD_DIR = "/tmp/rover_vision"  # Directory for dashboard rolling images (1-10)
STATUS_FILE = "/tmp/crop_monitor_v9.json"

# Vision Server paths (V9 change)
VISION_SERVER_DIR = "/tmp/vision_v9"
SOURCE_IMAGE = os.path.join(VISION_SERVER_DIR, "rgb_latest.jpg")
SOURCE_METADATA = os.path.join(VISION_SERVER_DIR, "rgb_latest.json")
VISION_STATUS_FILE = os.path.join(VISION_SERVER_DIR, "status.json")

# Create directories if they don't exist
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)


class SimpleCropMonitor:
    def __init__(self):
        self.running = True
        self.capture_count = 0
        self.last_capture_time = 0
        self.current_slot = 1  # Rolling slot number 1-10
        self.last_frame_number = 0  # V9: Track processed frames

    def check_vision_server(self):
        """Check if Vision Server is running and providing images."""
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

    def check_source_available(self):
        """Wait for Vision Server to start providing images."""
        print("Waiting for Vision Server...")
        
        for i in range(30):
            if os.path.exists(SOURCE_IMAGE) and os.path.exists(SOURCE_METADATA):
                # Check if Vision Server is actually running
                try:
                    with open(SOURCE_METADATA, 'r') as f:
                        meta = json.load(f)
                    age = time.time() - meta.get('timestamp', 0)
                    if age < 2.0:  # Frame is fresh
                        print(f"✓ Vision Server ready")
                        return True
                except (json.JSONDecodeError, KeyError, TypeError, ValueError, FileNotFoundError):
                    pass
            
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"  Still waiting... ({i}/30 seconds)")
        
        print(f"✗ Vision Server not ready after 30 seconds")
        print(f"   Make sure Vision Server (Component 196) is running first!")
        print(f"   Command: python3 realsense_vision_server_v9.py")
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
        """Copy image from Vision Server with deduplication."""
        if not os.path.exists(SOURCE_IMAGE):
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Vision Server image not available", end='')
            return False
        if not CV2_AVAILABLE:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ OpenCV not installed", end='')
            return False

        try:
            # V9: Read metadata to check frame number and freshness
            if os.path.exists(SOURCE_METADATA):
                try:
                    with open(SOURCE_METADATA, 'r') as f:
                        meta = json.load(f)
                    
                    # Validate metadata has required fields
                    if 'frame_number' not in meta or 'timestamp' not in meta:
                        # Metadata incomplete, try to process anyway
                        pass
                    else:
                        # Skip if we already processed this frame
                        if meta['frame_number'] == self.last_frame_number:
                            return False  # Same frame, skip
                        
                        # Check if frame is fresh (< 2 seconds old)
                        age = time.time() - meta['timestamp']
                        if age > 2.0:
                            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Frame is {age:.1f}s old", end='')
                            return False
                        
                        # Update tracking
                        self.last_frame_number = meta['frame_number']
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    # Metadata file corrupted or invalid, try to process image anyway
                    pass
            
            # Read image from Vision Server robustly
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
            
            # Try OpenCV first, fallback to PIL if needed
            ok_archive = False
            try:
                ok_archive = cv2.imwrite(archive_path, image, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if not ok_archive or not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
                    raise RuntimeError("OpenCV write failed or file is empty")
            except Exception:
                # Fallback to PIL
                if PIL_AVAILABLE:
                    try:
                        # Convert BGR to RGB for PIL
                        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(rgb_image)
                        pil_image.save(archive_path, 'JPEG', quality=70)
                        ok_archive = os.path.exists(archive_path) and os.path.getsize(archive_path) > 0
                    except Exception as e:
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ PIL fallback failed: {e}", end='')
                else:
                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ No PIL available for fallback", end='')

            # 2. Save to dashboard rolling buffer (1-10)
            dashboard_path = os.path.join(DASHBOARD_DIR, f"{self.current_slot}.jpg")
            
            # Ensure dashboard directory exists
            os.makedirs(DASHBOARD_DIR, exist_ok=True)
            
            ok_dash = False
            try:
                ok_dash = cv2.imwrite(dashboard_path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok_dash or not os.path.exists(dashboard_path) or os.path.getsize(dashboard_path) == 0:
                    raise RuntimeError("OpenCV write failed or file is empty")
            except Exception:
                # Fallback to PIL
                if PIL_AVAILABLE:
                    try:
                        # Convert BGR to RGB for PIL
                        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(rgb_image)
                        pil_image.save(dashboard_path, 'JPEG', quality=85)
                        ok_dash = os.path.exists(dashboard_path) and os.path.getsize(dashboard_path) > 0
                    except Exception as e:
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ PIL fallback failed for dashboard: {e}", end='')
                else:
                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ No PIL available for fallback", end='')

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
                'current_slot': self.current_slot,
                'last_frame_number': self.last_frame_number,
                'vision_server_connected': True
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
        print("Simple Crop Monitor V9 - Component 198")
        print("=" * 60)
        print(f"Source: Vision Server ({SOURCE_IMAGE})")
        print(f"Capture interval: {CAPTURE_INTERVAL} seconds")
        print(f"Archive directory: {IMAGE_DIR}")
        print(f"Dashboard slots: {DASHBOARD_DIR} (1-10)")
        print(f"Max archived images: {MAX_IMAGES}")
        print("=" * 60)

        if not self.check_source_available():
            print("✗ Vision Server not available - waiting and retrying...")
            # Keep waiting until source appears
            while not os.path.exists(SOURCE_IMAGE):
                time.sleep(1)
            print("✓ Source image detected, continuing...")

        print("\n✓ Crop monitor operational")
        print(f"  • Using images from Vision Server (V9)")
        print(f"  • Capturing 1 image every {CAPTURE_INTERVAL} seconds")
        print(f"  • Rolling archive of {MAX_IMAGES} images")
        print(f"  • Dashboard buffer: 10 slots")
        print(f"  • Frame deduplication: ENABLED")
        print()

        # Initialize all 10 dashboard slots
        print("Initializing dashboard slots (1-10)...")
        for i in range(10):
            success = self.capture_image()
            if success:
                print(f"\n  • Initialized slot {i+1}/10 ✓")
            else:
                print(f"\n  • Waiting for slot {i+1}/10...")
            time.sleep(0.5)
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
                            print(f"  Vision Server may have stopped")
                            # Check if Vision Server is still running
                            if not self.check_vision_server():
                                print(f"  ✗ Vision Server not responding")
                                print(f"  Waiting for Vision Server to restart...")
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

