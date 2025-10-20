#!/usr/bin/env python3
"""
Test hardware detection functionality
"""

import json
import os

def test_config_loading():
    """Test loading hardware configuration"""
    print("Testing hardware configuration loading...")
    
    config_file = "rover_config_v7.json"
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            print("✓ Config file found")
            print(f"  LIDAR Port: {config.get('lidar_port', 'Not found')}")
            print(f"  Pixhawk Port: {config.get('pixhawk_port', 'Not found')}")
            print(f"  RealSense Config: {config.get('realsense_config', 'Not found')}")
            
            # Test if ports exist
            lidar_port = config.get('lidar_port')
            pixhawk_port = config.get('pixhawk_port')
            
            if lidar_port and os.path.exists(lidar_port):
                print(f"✓ LIDAR port {lidar_port} exists")
            else:
                print(f"✗ LIDAR port {lidar_port} not found")
            
            if pixhawk_port and os.path.exists(pixhawk_port):
                print(f"✓ Pixhawk port {pixhawk_port} exists")
            else:
                print(f"✗ Pixhawk port {pixhawk_port} not found")
                
        except Exception as e:
            print(f"✗ Error loading config: {e}")
    else:
        print("✗ Config file not found - run rover_setup_v7.py first")

if __name__ == "__main__":
    print("Hardware Detection Test")
    print("=" * 40)
    test_config_loading()
