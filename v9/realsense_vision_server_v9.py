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
    try:
        from PIL import Image
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
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
# Use 424x240 for RGB to match depth resolution (compatible with all streams)
RGB_WIDTH = 424
RGB_HEIGHT = 240
RGB_FPS = 30  # 15fps not available at 640x480, use 30fps at 424x240
DEPTH_WIDTH = 424
DEPTH_HEIGHT = 240
DEPTH_FPS = 30  # Match RGB FPS for better sync

# Object Detection - uses RGB frames
OBJ_DETECT_ENABLED = True
OBJ_DETECT_CONFIDENCE_THRESHOLD = 0.5
OBJ_DETECT_NMS_THRESHOLD = 0.4

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
            'obj_detect_frames': 0,
            'errors': 0,
            'last_error': None,
            'last_error_time': None
        }
        
        # Initialize object detection
        self.obj_detector = None
        self.obj_classes = []
        self.obj_colors = []
        if OBJ_DETECT_ENABLED:
            self.init_object_detector()
        
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
    
    def init_object_detector(self):
        """Initialize object detection using OpenCV DNN with MobileNet-SSD."""
        try:
            # COCO class names (MobileNet-SSD uses COCO dataset)
            class_file = os.path.join(OUTPUT_DIR, "coco_classes.txt")
            if not os.path.exists(class_file):
                # Create default COCO classes file
                coco_classes = [
                    'background', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
                    'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
                    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
                    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
                    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
                    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
                    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant',
                    'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
                    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
                    'teddy bear', 'hair drier', 'toothbrush'
                ]
                with open(class_file, 'w') as f:
                    f.write('\n'.join(coco_classes))
            
            with open(class_file, 'r') as f:
                self.obj_classes = [line.strip() for line in f.readlines()]
            
            # Generate colors for each class
            np.random.seed(42)
            self.obj_colors = np.random.uniform(0, 255, size=(len(self.obj_classes), 3))
            
            # Model directory
            model_dir = os.path.join(OUTPUT_DIR, "models")
            os.makedirs(model_dir, exist_ok=True)
            
            prototxt = os.path.join(model_dir, "MobileNetSSD_deploy.prototxt")
            model = os.path.join(model_dir, "MobileNetSSD_deploy.caffemodel")
            
            # Download model files if not present
            if not os.path.exists(prototxt) or not os.path.exists(model):
                self.log("Downloading object detection model files...")
                try:
                    import urllib.request
                    
                    # Try multiple sources for model files
                    prototxt_urls = [
                        "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/MobileNetSSD_deploy.prototxt",
                        "https://github.com/opencv/opencv_extra/raw/master/testdata/dnn/MobileNetSSD_deploy.prototxt",
                        "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/MobileNetSSD_deploy.prototxt"
                    ]
                    
                    model_urls = [
                        "https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel",
                        "https://github.com/opencv/opencv_extra/raw/master/testdata/dnn/MobileNetSSD_deploy.caffemodel",
                        "https://drive.google.com/uc?export=download&id=0B3gersZ2cHIxRm5PMWR5ekN4SEU"
                    ]
                    
                    # Download prototxt
                    if not os.path.exists(prototxt):
                        self.log("  Downloading prototxt...")
                        downloaded = False
                        for url in prototxt_urls:
                            try:
                                urllib.request.urlretrieve(url, prototxt)
                                if os.path.exists(prototxt) and os.path.getsize(prototxt) > 1000:
                                    self.log(f"  ✓ Prototxt downloaded from: {url[:50]}...")
                                    downloaded = True
                                    break
                            except Exception as e:
                                continue
                        if not downloaded:
                            raise Exception("Failed to download prototxt from all sources")
                    
                    # Download model
                    if not os.path.exists(model):
                        self.log("  Downloading model weights (this may take 1-2 minutes, ~23MB)...")
                        self.log("  ⚠ Trying alternative sources...")
                        downloaded = False
                        for i, url in enumerate(model_urls):
                            try:
                                self.log(f"  Attempt {i+1}/{len(model_urls)}: {url[:60]}...")
                                urllib.request.urlretrieve(url, model)
                                if os.path.exists(model) and os.path.getsize(model) > 1000000:  # At least 1MB
                                    self.log(f"  ✓ Model weights downloaded ({os.path.getsize(model)/1024/1024:.1f}MB)")
                                    downloaded = True
                                    break
                            except Exception as e:
                                self.log(f"  ✗ Attempt {i+1} failed: {str(e)[:50]}")
                                continue
                        if not downloaded:
                            raise Exception("Failed to download model from all sources")
                    
                    self.log("  ✓ Model files downloaded successfully")
                except Exception as e:
                    self.log(f"  ✗ Failed to download model files: {e}")
                    self.log(f"  ⚠ Error details: {type(e).__name__}")
                    self.log("  ⚠ Object detection will use fallback mode")
                    self.log("  💡 To download manually, run: ./download_obj_detection_model.sh")
                    self.log(f"  💡 Or place model files in: {model_dir}")
                    self.obj_detector = None
                    return
            
            # Verify files exist
            if not os.path.exists(prototxt):
                self.log(f"✗ Prototxt file not found: {prototxt}")
                self.obj_detector = None
                return
            if not os.path.exists(model):
                self.log(f"✗ Model file not found: {model}")
                self.obj_detector = None
                return
            
            # Check file sizes
            prototxt_size = os.path.getsize(prototxt)
            model_size = os.path.getsize(model)
            self.log(f"  Model files: prototxt={prototxt_size} bytes, weights={model_size/1024/1024:.1f}MB")
            
            if model_size < 1000000:  # Less than 1MB is suspicious
                self.log(f"  ⚠ Model file seems too small ({model_size} bytes), may be corrupted")
            
            # Try to load the model
            try:
                self.log("Loading object detection model...")
                net = cv2.dnn.readNetFromCaffe(prototxt, model)
                if net is not None:
                    # Set backend and target (optional, for better performance)
                    try:
                        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    except:
                        pass
                    self.obj_detector = net
                    self.log(f"✓ Object detection initialized successfully (MobileNet-SSD)")
                    self.log(f"  Ready to detect objects with confidence threshold: {OBJ_DETECT_CONFIDENCE_THRESHOLD}")
                    return
                else:
                    self.log("✗ Model loaded but returned None")
            except Exception as e:
                self.log(f"✗ Failed to load model: {e}")
                self.log(f"  Error type: {type(e).__name__}")
                import traceback
                self.log(f"  Traceback: {traceback.format_exc()}")
            
        except Exception as e:
            self.log(f"⚠ Object detection init failed: {e}")
            self.obj_detector = None
    
    def detect_objects(self, color_image):
        """Detect objects in RGB frame and return annotated image."""
        annotated = color_image.copy()
        
        if self.obj_detector is None:
            # Fallback: draw a message indicating model status
            h, w = color_image.shape[:2]
            
            # Check if model files exist to determine message
            model_dir = os.path.join(OUTPUT_DIR, "models")
            prototxt = os.path.join(model_dir, "MobileNetSSD_deploy.prototxt")
            model = os.path.join(model_dir, "MobileNetSSD_deploy.caffemodel")
            
            if os.path.exists(prototxt) and os.path.exists(model):
                text = "Object Detection: Model Failed to Load"
                color = (0, 0, 255)  # Red
            else:
                text = "Object Detection: Downloading Model..."
                color = (0, 255, 255)  # Cyan
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            
            # Draw background rectangle
            cv2.rectangle(annotated, (10, 10), (10 + text_width + 10, 10 + text_height + baseline + 10),
                         (0, 0, 0), -1)
            # Draw text
            cv2.putText(annotated, text, (15, 15 + text_height), font, font_scale, color, thickness)
            
            # Add instruction text
            inst_text = "Check logs for details"
            inst_size, _ = cv2.getTextSize(inst_text, font, 0.4, 1)
            cv2.putText(annotated, inst_text, (15, 15 + text_height + baseline + 20), 
                       font, 0.4, (128, 128, 128), 1)
            
            return annotated
        
        try:
            h, w = color_image.shape[:2]
            # MobileNet-SSD expects 300x300 input
            blob = cv2.dnn.blobFromImage(cv2.resize(color_image, (300, 300)), 0.007843, (300, 300), 127.5)
            self.obj_detector.setInput(blob)
            detections = self.obj_detector.forward()
            
            detection_count = 0
            
            # Process detections
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                
                if confidence > OBJ_DETECT_CONFIDENCE_THRESHOLD:
                    class_id = int(detections[0, 0, i, 1])
                    if class_id >= len(self.obj_classes):
                        continue
                    
                    # Get bounding box
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    # Ensure coordinates are within image bounds
                    startX = max(0, min(startX, w))
                    startY = max(0, min(startY, h))
                    endX = max(0, min(endX, w))
                    endY = max(0, min(endY, h))
                    
                    # Skip if box is too small or invalid
                    if endX - startX < 10 or endY - startY < 10:
                        continue
                    
                    # Draw bounding box and label
                    label = f"{self.obj_classes[class_id]}: {confidence:.2f}"
                    color = self.obj_colors[class_id].astype(int).tolist()
                    
                    # Draw thicker box
                    cv2.rectangle(annotated, (startX, startY), (endX, endY), color, 2)
                    
                    # Draw label background
                    label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    label_y = max(startY, label_size[1] + 10)
                    cv2.rectangle(annotated, (startX, label_y - label_size[1] - 10),
                                     (startX + label_size[0], label_y + 5), color, -1)
                    cv2.putText(annotated, label, (startX, label_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    detection_count += 1
            
            # Log detection count periodically (avoid spam)
            if hasattr(self, '_last_detection_log'):
                if time.time() - self._last_detection_log > 5.0:
                    if detection_count > 0:
                        self.log(f"Object detection: {detection_count} objects found")
                    else:
                        # Log when no detections to help debug
                        if hasattr(self, '_no_detection_count'):
                            self._no_detection_count += 1
                        else:
                            self._no_detection_count = 1
                        if self._no_detection_count % 10 == 0:  # Every 10 frames
                            self.log(f"Object detection: No objects detected (confidence threshold: {OBJ_DETECT_CONFIDENCE_THRESHOLD})")
                    self._last_detection_log = time.time()
            else:
                self._last_detection_log = time.time()
                self._no_detection_count = 0
            
            # Draw detection status on image if no objects found
            if detection_count == 0:
                h, w = annotated.shape[:2]
                status_text = f"No objects detected (threshold: {OBJ_DETECT_CONFIDENCE_THRESHOLD})"
                cv2.putText(annotated, status_text, (10, h - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
            
            return annotated
            
        except Exception as e:
            self.log(f"✗ Object detection error: {e}")
            # Draw error message on image
            h, w = color_image.shape[:2]
            text = f"Detection Error: {str(e)[:30]}"
            cv2.putText(annotated, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            return annotated
    
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
            
            # Try OpenCV first, fallback to PIL if OpenCV doesn't support JPEG
            success = False
            try:
                success = cv2.imwrite(rgb_tmp, color_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if success and os.path.exists(rgb_tmp) and os.path.getsize(rgb_tmp) > 0:
                    os.replace(rgb_tmp, rgb_path)
                else:
                    success = False
            except:
                success = False
            
            # Fallback to PIL if OpenCV failed
            if not success and PIL_AVAILABLE:
                try:
                    # Convert BGR to RGB for PIL
                    rgb_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_image)
                    pil_image.save(rgb_tmp, 'JPEG', quality=85)
                    if os.path.exists(rgb_tmp) and os.path.getsize(rgb_tmp) > 0:
                        os.replace(rgb_tmp, rgb_path)
                        success = True
                except Exception as pil_error:
                    self.log(f"✗ PIL fallback also failed: {pil_error}")
                    success = False
            
            if not success:
                raise RuntimeError("Failed to write JPEG with both OpenCV and PIL")
            
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
                
                # Try OpenCV first, fallback to PIL
                success = False
                try:
                    success = cv2.imwrite(dj_tmp, depth_color, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if success and os.path.exists(dj_tmp) and os.path.getsize(dj_tmp) > 0:
                        os.replace(dj_tmp, dj_path)
                        success = True
                    else:
                        success = False
                except:
                    success = False
                
                # Fallback to PIL if OpenCV failed
                if not success and PIL_AVAILABLE:
                    try:
                        # Convert BGR to RGB for PIL
                        rgb_color = cv2.cvtColor(depth_color, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(rgb_color)
                        pil_image.save(dj_tmp, 'JPEG', quality=85)
                        if os.path.exists(dj_tmp) and os.path.getsize(dj_tmp) > 0:
                            os.replace(dj_tmp, dj_path)
                            success = True
                    except:
                        pass
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

    def write_obj_detect_frame(self, color_image):
        """Write object detection annotated frame."""
        try:
            timestamp = time.time()
            
            # Detect objects and create annotated image
            annotated_image = self.detect_objects(color_image)
            
            obj_tmp = os.path.join(OUTPUT_DIR, "obj_detect_latest.jpg.tmp")
            obj_path = os.path.join(OUTPUT_DIR, "obj_detect_latest.jpg")
            
            # Try OpenCV first, fallback to PIL
            success = False
            try:
                success = cv2.imwrite(obj_tmp, annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if success and os.path.exists(obj_tmp) and os.path.getsize(obj_tmp) > 0:
                    os.replace(obj_tmp, obj_path)
                else:
                    success = False
            except:
                success = False
            
            # Fallback to PIL if OpenCV failed
            if not success and PIL_AVAILABLE:
                try:
                    # Convert BGR to RGB for PIL
                    rgb_image = cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_image)
                    pil_image.save(obj_tmp, 'JPEG', quality=85)
                    if os.path.exists(obj_tmp) and os.path.getsize(obj_tmp) > 0:
                        os.replace(obj_tmp, obj_path)
                        success = True
                except Exception as pil_error:
                    self.log(f"✗ PIL fallback for object detection failed: {pil_error}")
                    success = False
            
            if not success:
                raise RuntimeError("Failed to write object detection JPEG with both OpenCV and PIL")
            
            # Write metadata
            meta_tmp = os.path.join(OUTPUT_DIR, "obj_detect_latest.json.tmp")
            meta_path = os.path.join(OUTPUT_DIR, "obj_detect_latest.json")
            metadata = {
                'frame_number': self.frame_number,
                'timestamp': timestamp,
                'timestamp_iso': datetime.fromtimestamp(timestamp).isoformat(),
                'width': RGB_WIDTH,
                'height': RGB_HEIGHT,
                'fps_target': RGB_FPS,
                'detection_enabled': OBJ_DETECT_ENABLED
            }
            with open(meta_tmp, 'w') as f:
                json.dump(metadata, f)
            os.replace(meta_tmp, meta_path)
            
            self.stats['obj_detect_frames'] += 1
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
            obj_detect_fps = self.stats['obj_detect_frames'] / uptime if uptime > 0 else 0
            
            status = {
                'component_id': COMPONENT_ID,
                'component_name': 'RealSense Vision Server V9',
                'status': 'RUNNING',
                'uptime_seconds': int(uptime),
                'frames_processed': {
                    'rgb': self.stats['rgb_frames'],
                    'depth': self.stats['depth_frames'],
                    'obj_detect': self.stats['obj_detect_frames']
                },
                'fps': {
                    'rgb_actual': round(rgb_fps, 1),
                    'depth_actual': round(depth_fps, 1),
                    'obj_detect_actual': round(obj_detect_fps, 1),
                    'rgb_target': RGB_FPS,
                    'depth_target': DEPTH_FPS
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
                
                # Get color and depth frames
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                
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
                
                # Object detection (replaces IR)
                if OBJ_DETECT_ENABLED:
                    self.write_obj_detect_frame(color_image)
                
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

