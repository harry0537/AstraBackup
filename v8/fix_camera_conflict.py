#!/usr/bin/env python3
"""
Camera Conflict Resolution Script
Helps resolve RealSense camera resource conflicts
"""

import os
import subprocess
import time
import signal

def kill_camera_processes():
    """Kill all processes that might be using the camera"""
    print("=== KILLING CAMERA PROCESSES ===")
    
    processes_to_kill = [
        'simple_crop_monitor',
        'combo_proximity_bridge', 
        'rover_manager',
        'realsense-viewer',
        'rs-enumerate-devices'
    ]
    
    for process in processes_to_kill:
        try:
            result = subprocess.run(['pkill', '-f', process], capture_output=True)
            if result.returncode == 0:
                print(f"  ✓ Killed {process}")
            else:
                print(f"  - No {process} processes found")
        except Exception as e:
            print(f"  ✗ Error killing {process}: {e}")

def reset_camera():
    """Reset camera by unplugging/replugging USB"""
    print("\n=== RESETTING CAMERA ===")
    print("  Please unplug and replug the RealSense camera USB cable")
    print("  Wait 5 seconds after replugging...")
    
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    
    print("  ✓ Camera reset complete")

def test_camera():
    """Test if camera is accessible"""
    print("\n=== TESTING CAMERA ===")
    
    try:
        import pyrealsense2 as rs
        
        ctx = rs.context()
        devices = ctx.query_devices()
        
        if len(devices) == 0:
            print("  ✗ No RealSense devices found")
            return False
            
        print(f"  ✓ Found {len(devices)} RealSense device(s)")
        
        # Try to create a simple pipeline
        try:
            pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
            
            pipeline.start(config)
            frames = pipeline.wait_for_frames(timeout_ms=2000)
            color_frame = frames.get_color_frame()
            
            if color_frame:
                print("  ✓ Camera is accessible")
                pipeline.stop()
                return True
            else:
                print("  ✗ Camera not responding")
                pipeline.stop()
                return False
                
        except Exception as e:
            print(f"  ✗ Camera test failed: {e}")
            return False
            
    except ImportError:
        print("  ✗ pyrealsense2 not available")
        return False

def main():
    print("REALSENSE CAMERA CONFLICT RESOLVER")
    print("=" * 50)
    
    # Step 1: Kill all camera processes
    kill_camera_processes()
    
    # Step 2: Wait a moment
    print("\nWaiting 3 seconds...")
    time.sleep(3)
    
    # Step 3: Test camera
    if test_camera():
        print("\n✓ Camera is now accessible!")
        print("\nYou can now run:")
        print("  python3 simple_crop_monitor_v8.py")
        print("  python3 rover_manager_v8.py")
    else:
        print("\n⚠ Camera still not accessible")
        print("\nTry:")
        print("1. Unplug and replug the RealSense camera")
        print("2. Run: sudo modprobe uvcvideo")
        print("3. Run: sudo udevadm control --reload-rules")
        print("4. Restart the system")

if __name__ == "__main__":
    main()
