#!/usr/bin/env python3
"""
Test RC Override - Direct test to verify rover responds to commands
Use this to diagnose why rover isn't moving
"""

import time
import os
import sys
from pymavlink import mavutil

# Load config
def load_config():
    config_file = "rover_config_v9.json"
    default_port = '/dev/ttyACM0'
    default_baud = 57600
    
    if os.path.exists(config_file):
        try:
            import json
            with open(config_file, 'r') as f:
                config = json.load(f)
                prox_config = config.get('proximity_bridge', {})
                return {
                    'port': prox_config.get('pixhawk_port', default_port),
                    'baud': prox_config.get('pixhawk_baud', default_baud)
                }
        except:
            pass
    
    return {'port': default_port, 'baud': default_baud}

config = load_config()
PIXHAWK_PORT = config['port']
PIXHAWK_BAUD = config['baud']

def test_rc_override():
    """Test RC override with manual commands"""
    print("=" * 60)
    print("RC Override Test Script")
    print("=" * 60)
    print(f"Connecting to Pixhawk at {PIXHAWK_PORT}...")
    
    # Connect
    try:
        candidates = [PIXHAWK_PORT] + [f'/dev/ttyACM{i}' for i in range(4)]
        mavlink = None
        
        for port in candidates:
            if not os.path.exists(port):
                continue
            try:
                print(f"  Trying {port}...")
                mavlink = mavutil.mavlink_connection(port, baud=PIXHAWK_BAUD)
                mavlink.wait_heartbeat(timeout=5)
                print(f"✓ Connected to {port}")
                break
            except:
                continue
        
        if not mavlink:
            print("✗ Failed to connect to Pixhawk")
            return
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return
    
    # Get system info
    print("\nSystem Info:")
    print(f"  System ID: {mavlink.target_system}")
    print(f"  Component ID: {mavlink.target_component}")
    
    # Test sequence
    print("\n" + "=" * 60)
    print("RC Override Test Sequence")
    print("=" * 60)
    print("\n⚠️  WARNING: Rover will move!")
    print("   Make sure rover is on ground and safe to move")
    print("   Press Ctrl+C to stop immediately")
    print("\nStarting in 5 seconds...")
    time.sleep(5)
    
    test_sequence = [
        ("Stop", 1500, 1500, 2),
        ("Forward Slow", 1500, 1520, 3),
        ("Forward Medium", 1500, 1600, 3),
        ("Forward Fast", 1500, 1650, 3),
        ("Stop", 1500, 1500, 2),
        ("Turn Right", 1640, 1600, 3),
        ("Turn Left", 1360, 1600, 3),
        ("Stop", 1500, 1500, 2),
    ]
    
    try:
        for name, steer, throttle, duration in test_sequence:
            print(f"\n[{name}] Steer:{steer} Throttle:{throttle} ({duration}s)")
            
            start_time = time.time()
            while time.time() - start_time < duration:
                # Send command at 10Hz
                mavlink.mav.rc_channels_override_send(
                    mavlink.target_system,
                    mavlink.target_component,
                    steer,      # Channel 1
                    0,          # Channel 2
                    throttle,   # Channel 3
                    0,          # Channel 4
                    0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0
                )
                mavlink.flush()
                time.sleep(0.1)
            
            print(f"  ✓ Command sent")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  STOPPED - Sending stop command...")
        mavlink.mav.rc_channels_override_send(
            mavlink.target_system,
            mavlink.target_component,
            1500, 1500, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0,
            0, 0
        )
        mavlink.flush()
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    print("\nDid the rover move?")
    print("  • If YES: RC override works, check navigation script")
    print("  • If NO: Check channel mapping, ESC calibration, or hardware")

if __name__ == "__main__":
    test_rc_override()

