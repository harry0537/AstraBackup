#!/usr/bin/env python3
"""
Crop Monitor Diagnostic Tool for Ubuntu/Linux
Checks common failure points that could cause the crop monitor to stop
"""

import os
import sys
import json
import subprocess
import time
import stat

def check_realsense_availability():
    """Check if RealSense is available and working"""
    print("=== REALSENSE CAMERA ===")
    
    try:
        import pyrealsense2 as rs
        print("  pyrealsense2 library: OK Available")
        
        # Try to create pipeline
        try:
            pipeline = rs.pipeline()
            config = rs.config()
            print("  Pipeline creation: OK")
        except Exception as e:
            print(f"  Pipeline creation: ERROR - {e}")
            return False
            
        # Try to detect devices
        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            if len(devices) > 0:
                print(f"  Devices found: OK ({len(devices)} device(s))")
                for i, device in enumerate(devices):
                    print(f"    Device {i}: {device.get_info(rs.camera_info.name)}")
            else:
                print("  Devices found: ERROR - No RealSense devices detected")
                return False
        except Exception as e:
            print(f"  Device detection: ERROR - {e}")
            return False
            
        return True
        
    except ImportError as e:
        print(f"  pyrealsense2 library: MISSING - {e}")
        return False

def check_camera_configurations():
    """Test different camera configurations"""
    print("\n=== CAMERA CONFIGURATIONS ===")
    
    try:
        import pyrealsense2 as rs
        
        pipeline = rs.pipeline()
        configs_to_try = [
            (rs.stream.color, 1280, 720, rs.format.bgr8, 30),
            (rs.stream.color, 640, 480, rs.format.bgr8, 30),
            (rs.stream.color, 848, 480, rs.format.bgr8, 30),
            (rs.stream.color, 640, 480, rs.format.bgr8, 15),
        ]
        
        for i, (stream, width, height, format, fps) in enumerate(configs_to_try):
            try:
                print(f"  Testing {width}x{height} @ {fps}fps...", end='')
                config = rs.config()
                config.enable_stream(stream, width, height, format, fps)
                pipeline.start(config)
                
                # Test frame capture
                frames = pipeline.wait_for_frames(timeout_ms=2000)
                color_frame = frames.get_color_frame()
                if color_frame:
                    print(" OK")
                    pipeline.stop()
                    return True
                else:
                    print(" FAILED - No color frame")
                    pipeline.stop()
            except Exception as e:
                print(f" FAILED - {e}")
                try:
                    pipeline.stop()
                except:
                    pass
                    
        print("  All configurations failed")
        return False
        
    except Exception as e:
        print(f"  Configuration test failed: {e}")
        return False

def check_opencv_availability():
    """Check if OpenCV is available"""
    print("\n=== OPENCV ===")
    
    try:
        import cv2
        print("  OpenCV library: OK Available")
        print(f"  OpenCV version: {cv2.__version__}")
        return True
    except ImportError as e:
        print(f"  OpenCV library: MISSING - {e}")
        return False
    except Exception as e:
        print(f"  OpenCV error: {e}")
        return False

def check_temp_directory():
    """Check temp directory permissions"""
    print("\n=== TEMP DIRECTORY ===")
    
    temp_file = "/tmp/crop_latest.jpg"
    status_file = "/tmp/crop_monitor_v8.json"
    
    # Check /tmp exists and is writable
    if os.path.exists("/tmp"):
        print("  /tmp directory: OK")
        try:
            test_file = "/tmp/test_crop_write.tmp"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print("  Write permissions: OK")
        except Exception as e:
            print(f"  Write permissions: ERROR - {e}")
            return False
    else:
        print("  /tmp directory: MISSING")
        return False
    
    # Check if files exist
    if os.path.exists(temp_file):
        size = os.path.getsize(temp_file)
        mtime = os.path.getmtime(temp_file)
        age = time.time() - mtime
        print(f"  Crop image file: OK ({size} bytes, {age:.1f}s old)")
    else:
        print("  Crop image file: MISSING")
    
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                data = json.load(f)
            print(f"  Status file: OK (captures: {data.get('capture_count', 0)})")
        except Exception as e:
            print(f"  Status file: ERROR - {e}")
    else:
        print("  Status file: MISSING")

def check_running_processes():
    """Check if crop monitor is already running"""
    print("\n=== RUNNING PROCESSES ===")
    
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            crop_processes = [line for line in lines if 'simple_crop_monitor' in line or 'crop_monitor' in line]
            if crop_processes:
                print("  Crop monitor processes found:")
                for proc in crop_processes:
                    print(f"    {proc}")
            else:
                print("  No crop monitor processes running")
        else:
            print("  Process check failed")
    except Exception as e:
        print(f"  Process check error: {e}")

def check_usb_devices():
    """Check USB devices for RealSense"""
    print("\n=== USB DEVICES ===")
    
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            realsense_devices = [line for line in lines if 'RealSense' in line or 'Intel' in line]
            if realsense_devices:
                print("  RealSense devices found:")
                for device in realsense_devices:
                    print(f"    {device}")
            else:
                print("  No RealSense devices found")
        else:
            print("  lsusb command failed")
    except Exception as e:
        print(f"  USB check error: {e}")

def test_crop_monitor_manually():
    """Test crop monitor components manually"""
    print("\n=== MANUAL TEST ===")
    
    try:
        # Test RealSense connection
        import pyrealsense2 as rs
        import cv2
        import numpy as np
        
        print("  Testing RealSense connection...")
        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        
        print("  Starting pipeline...")
        pipeline.start(config)
        
        print("  Capturing test frame...")
        frames = pipeline.wait_for_frames(timeout_ms=5000)
        color_frame = frames.get_color_frame()
        
        if color_frame:
            print("  Converting to numpy array...")
            image = np.asanyarray(color_frame.get_data())
            print(f"  Image shape: {image.shape}")
            
            print("  Saving test image...")
            test_path = "/tmp/crop_test.jpg"
            cv2.imwrite(test_path, image, [cv2.IMWRITE_JPEG_QUALITY, 75])
            
            if os.path.exists(test_path):
                size = os.path.getsize(test_path)
                print(f"  Test image saved: OK ({size} bytes)")
                os.remove(test_path)
            else:
                print("  Test image save: FAILED")
                
        else:
            print("  Frame capture: FAILED - No color frame")
            
        pipeline.stop()
        print("  Pipeline stopped: OK")
        return True
        
    except Exception as e:
        print(f"  Manual test failed: {e}")
        return False

def main():
    print("CROP MONITOR DIAGNOSTIC TOOL (UBUNTU)")
    print("=" * 50)
    
    realsense_ok = check_realsense_availability()
    opencv_ok = check_opencv_availability()
    config_ok = check_camera_configurations()
    check_temp_directory()
    check_running_processes()
    check_usb_devices()
    
    if realsense_ok and opencv_ok:
        test_crop_monitor_manually()
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")
    print("\nCommon fixes:")
    print("1. Install missing libraries: pip3 install pyrealsense2 opencv-python")
    print("2. Check USB connection: lsusb | grep RealSense")
    print("3. Kill existing processes: pkill -f simple_crop_monitor")
    print("4. Check permissions: ls -la /tmp/")

if __name__ == "__main__":
    main()
