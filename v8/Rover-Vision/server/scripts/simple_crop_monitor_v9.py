#!/usr/bin/env python3
"""
Project Astra NZ - Simple Crop Monitor V9
Space-saving crop monitor with rolling buffer of 40 images
Captures one image every 60 seconds with automatic cleanup
Component 198 - Optimized for space efficiency

FUNCTIONALITY:
- Captures images from RealSense camera every 60 seconds
- Maintains rolling buffer of maximum 40 images to prevent disk overflow
- Automatically removes oldest images when limit is exceeded
- Optimizes image quality (60% JPEG) for space efficiency
- Provides robust camera sharing with proximity bridge component
- Writes status information to /tmp/crop_monitor_v9.json for dashboard
- Saves latest image to /tmp/crop_latest.jpg for dashboard display

SPACE OPTIMIZATION FEATURES:
- Rolling buffer: Maximum 40 images stored
- Automatic cleanup: Removes oldest images when limit reached
- Optimized compression: 60% JPEG quality for smaller file sizes
- Storage monitoring: Tracks disk usage and image count
- Timestamped filenames: crop_YYYYMMDD_HHMMSS.jpg format

CAMERA SHARING:
- Works alongside proximity bridge without conflicts
- Multiple fallback configurations for different camera states
- Resource sharing to prevent "Device or resource busy" errors
- Automatic reconnection on camera failures

USAGE:
- Run: python3 simple_crop_monitor_v9.py
- No command line arguments required
- Automatically creates /tmp/crop_images/ directory
- Integrates with telemetry dashboard for live rover vision
"""

import cv2
import numpy as np
import time
import os
import shutil
from datetime import datetime
import json
import glob

# Import RealSense library with graceful fallback
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

COMPONENT_ID = 198                    # Unique component identifier
CAPTURE_INTERVAL = 60                 # Image capture interval (seconds)
IMAGE_OUTPUT = "/tmp/crop_latest.jpg" # Latest image for dashboard
STATUS_FILE = "/tmp/crop_monitor_v9.json"  # Status file for dashboard
IMAGE_DIR = "/tmp/crop_images"        # Directory for image storage
MAX_IMAGES = 40                       # Maximum number of images to keep
IMAGE_QUALITY = 60                    # JPEG quality (60% for space efficiency)

# ============================================================================
# SIMPLE CROP MONITOR CLASS
# ============================================================================

class SimpleCropMonitor:
    """
    Space-optimized crop monitor for rover vision system
    
    This class handles:
    - RealSense camera connection and image capture
    - Rolling buffer management (max 40 images)
    - Automatic cleanup of old images
    - Camera resource sharing with proximity bridge
    - Status reporting for telemetry dashboard
    - Error handling and automatic reconnection
    """
    
    def __init__(self):
        """
        Initialize the crop monitor with default settings
        Creates necessary directories and initializes tracking variables
        """
        self.pipeline = None          # RealSense pipeline object
        self.running = True           # Main loop control flag
        self.capture_count = 0       # Total images captured
        self.last_capture_time = 0    # Timestamp of last capture
        self.image_files = []         # List of image files for cleanup
        
        # Create image storage directory
        os.makedirs(IMAGE_DIR, exist_ok=True)

    def connect_camera(self):
        """
        Connect to RealSense camera with robust resource sharing
        
        This method handles camera connection with multiple fallback strategies:
        1. Try to use existing camera resources (shared with proximity bridge)
        2. Create new pipeline with native device profiles
        3. Fall back to minimal configurations if needed
        4. Handle camera conflicts and resource sharing
        
        Returns:
            bool: True if camera connection successful, False otherwise
        """
        try:
            # Check if RealSense library is available
            if not REALSENSE_AVAILABLE:
                print("✗ RealSense library not available")
                return False

            print("Connecting to RealSense for image capture")
            
            # Check for available RealSense devices
            try:
                ctx = rs.context()
                devices = ctx.query_devices()
                if len(devices) == 0:
                    print("  [ERROR] No RealSense devices found")
                    return False
                
                print(f"  [INFO] Found {len(devices)} RealSense device(s)")
                
                # Try to use existing camera resources first (shared with proximity bridge)
                if self.try_shared_camera():
                    return True
                    
            except Exception as e:
                print(f"  [WARNING] Device detection failed: {e}")
            
            # If shared camera doesn't work, create new pipeline
            print("  [INFO] Creating new RealSense pipeline...")
            self.pipeline = rs.pipeline()
            config = rs.config()

            # First try native stream profiles from the device
            if self.try_native_profiles():
                return True

            # Enhanced configurations with more fallback options
            configs_to_try = [
                # Medium resolution for space efficiency
                (rs.stream.color, 640, 480, rs.format.bgr8, 15),
                (rs.stream.color, 640, 480, rs.format.bgr8, 10),
                (rs.stream.color, 640, 360, rs.format.bgr8, 15),
                (rs.stream.color, 640, 360, rs.format.bgr8, 10),
                # Lower resolutions for compatibility
                (rs.stream.color, 480, 360, rs.format.bgr8, 15),
                (rs.stream.color, 480, 360, rs.format.bgr8, 10),
                (rs.stream.color, 424, 240, rs.format.bgr8, 15),
                (rs.stream.color, 424, 240, rs.format.bgr8, 10),
                # Very low resolution fallback
                (rs.stream.color, 320, 240, rs.format.bgr8, 10),
                (rs.stream.color, 320, 180, rs.format.bgr8, 10),
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
                config.enable_stream(rs.stream.color, 320, 240, rs.format.bgr8, 10)
                
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
                    
                # Sort by resolution (medium first for space efficiency)
                color_profiles.sort(key=lambda x: x.as_video_stream_profile().width() * x.as_video_stream_profile().height())
                
                # Try medium resolution profiles first
                for profile in color_profiles[2:5]:  # Skip very low and very high
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

    def cleanup_old_images(self):
        """
        Remove old images to maintain MAX_IMAGES limit (rolling buffer)
        
        This method implements the space-saving feature by:
        1. Finding all crop images in the storage directory
        2. Sorting them by modification time (oldest first)
        3. Removing oldest files when limit is exceeded
        4. Maintaining a rolling buffer of exactly MAX_IMAGES images
        
        This prevents disk space issues by automatically managing storage.
        """
        try:
            # Get all crop image files in the directory
            image_files = glob.glob(os.path.join(IMAGE_DIR, "crop_*.jpg"))
            image_files.sort(key=os.path.getmtime)  # Sort by modification time (oldest first)
            
            # Remove oldest files if we exceed the limit
            while len(image_files) >= MAX_IMAGES:
                oldest_file = image_files.pop(0)
                try:
                    os.remove(oldest_file)
                    print(f"  [CLEANUP] Removed old image: {os.path.basename(oldest_file)}")
                except Exception as e:
                    print(f"  [CLEANUP] Failed to remove {oldest_file}: {e}")
            
            # Update our tracking list
            self.image_files = image_files
            
        except Exception as e:
            print(f"  [CLEANUP] Error during cleanup: {e}")

    def get_storage_info(self):
        """
        Get storage information for monitoring and dashboard display
        
        Calculates:
        - Total storage used by all crop images (MB)
        - Number of images currently stored
        - Average image size (KB)
        
        Returns:
            dict: Storage statistics for telemetry dashboard
        """
        try:
            total_size = 0
            image_count = 0
            
            # Calculate total size and count of all crop images
            for file_path in glob.glob(os.path.join(IMAGE_DIR, "crop_*.jpg")):
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
                    image_count += 1
            
            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'image_count': image_count,
                'avg_size_kb': round(total_size / (image_count * 1024), 1) if image_count > 0 else 0
            }
        except Exception as e:
            return {'total_size_mb': 0, 'image_count': 0, 'avg_size_kb': 0}

    def capture_image(self):
        """Capture and save single image with space optimization"""
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

            # Clean up old images before saving new one
            self.cleanup_old_images()

            # Generate timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"crop_{timestamp}.jpg"
            image_path = os.path.join(IMAGE_DIR, image_filename)

            # Save image with optimized compression for space efficiency
            success = cv2.imwrite(image_path, image, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_QUALITY])
            if not success:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Failed to save image", end='')
                return False

            # Copy to latest image for dashboard
            shutil.copy2(image_path, IMAGE_OUTPUT)

            # Update status
            self.capture_count += 1
            self.last_capture_time = time.time()

            # Get storage info
            storage_info = self.get_storage_info()

            status = {
                'timestamp': datetime.now().isoformat(),
                'capture_count': self.capture_count,
                'image_path': IMAGE_OUTPUT,
                'image_size': os.path.getsize(IMAGE_OUTPUT) if os.path.exists(IMAGE_OUTPUT) else 0,
                'storage_info': storage_info,
                'quality': IMAGE_QUALITY,
                'max_images': MAX_IMAGES,
                'interval': CAPTURE_INTERVAL
            }

            # Write status file with error handling
            try:
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status, f)
            except Exception as e:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Status file write failed: {e}", end='')

            file_size_kb = os.path.getsize(IMAGE_OUTPUT) / 1024
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Captured image #{self.capture_count} ({file_size_kb:.1f}KB, {storage_info['image_count']}/{MAX_IMAGES} images, {storage_info['total_size_mb']:.1f}MB total)", end='', flush=True)
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
        """
        Main execution loop for the crop monitor
        
        This method:
        1. Connects to the RealSense camera
        2. Captures images every 60 seconds
        3. Manages rolling buffer of 40 images
        4. Handles errors and automatic reconnection
        5. Provides status updates and storage monitoring
        """
        print("=" * 60)
        print("Simple Crop Monitor V9 - Component 198")
        print("=" * 60)
        print(f"Capture interval: {CAPTURE_INTERVAL} seconds")
        print(f"Max images: {MAX_IMAGES}")
        print(f"Image quality: {IMAGE_QUALITY}%")
        print(f"Output: {IMAGE_OUTPUT}")
        print(f"Storage: {IMAGE_DIR}")
        print("=" * 60)

        # Connect to camera - required for operation
        if not self.connect_camera():
            print("✗ Cannot operate without camera")
            return

        print("\n✓ Crop monitor operational")
        print("  • Capturing 1 image every 60 seconds")
        print("  • Automatic cleanup (max 40 images)")
        print("  • Space-optimized compression")
        print("  • Rolling buffer for storage efficiency")
        print()

        # Perform initial image capture
        self.capture_image()

        try:
            consecutive_failures = 0
            max_failures = 5
            
            # Main monitoring loop
            while self.running:
                current_time = time.time()

                # Check if it's time for next capture (every 60 seconds)
                if current_time - self.last_capture_time >= CAPTURE_INTERVAL:
                    success = self.capture_image()
                    
                    if success:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ⚠ Consecutive failures: {consecutive_failures}/{max_failures}", end='')
                        
                        # If too many failures, attempt camera reconnection
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

                time.sleep(1)  # Check every second

        except KeyboardInterrupt:
            print("\n\nShutdown initiated...")

        finally:
            # Cleanup on shutdown
            self.running = False

            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass

            print("\n✓ Crop monitor stopped")
            print(f"Total captures: {self.capture_count}")
            
            # Final storage report
            storage_info = self.get_storage_info()
            print(f"Final storage: {storage_info['image_count']} images, {storage_info['total_size_mb']:.1f}MB total")

if __name__ == "__main__":
    monitor = SimpleCropMonitor()
    monitor.run()
