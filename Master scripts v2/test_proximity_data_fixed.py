#!/usr/bin/env python3
"""
Enhanced MAVLink Data Verification - Tests Both Direct and MAVProxy Connections
"""

from pymavlink import mavutil
import time

def test_direct_connection():
    """Test direct connection to LiDAR bridge"""
    print("🎯 Testing direct LiDAR bridge connection...")
    try:
        mavlink = mavutil.mavlink_connection('udpin:127.0.0.1:14551')
        print("Waiting for DISTANCE_SENSOR messages from LiDAR bridge...")
        
        for i in range(10):
            msg = mavlink.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=2)
            if msg:
                angle = (msg.id - 1) * 5  # Convert sector back to angle
                print(f"✅ Sector {msg.id}: {msg.current_distance}cm at {angle}°")
                return True
            print(f"Waiting... {i+1}/10")
        
        print("❌ No direct DISTANCE_SENSOR messages received")
        return False
        
    except Exception as e:
        print(f"❌ Direct connection error: {e}")
        return False

def test_mavproxy_connection():
    """Test connection through MAVProxy to Mission Planner"""
    print("\n🎯 Testing MAVProxy relay connection...")
    try:
        mavlink = mavutil.mavlink_connection('udpin:127.0.0.1:14550')
        print("Waiting for DISTANCE_SENSOR messages from MAVProxy...")
        
        for i in range(15):
            msg = mavlink.recv_match(type='DISTANCE_SENSOR', blocking=True, timeout=2)
            if msg:
                angle = (msg.id - 1) * 5
                print(f"✅ MAVProxy relay - Sector {msg.id}: {msg.current_distance}cm at {angle}°")
                return True
            print(f"Waiting... {i+1}/15")
        
        print("❌ No MAVProxy DISTANCE_SENSOR messages received")
        return False
        
    except Exception as e:
        print(f"❌ MAVProxy connection error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Enhanced MAVLink Data Verification")
    print("=" * 50)
    
    print("\nMake sure these are running:")
    print("1. start_mavproxy.sh (fixed version)")
    print("2. lidar_mavlink_bridge.py (fixed version)")
    print()
    
    # Test both connections
    direct_ok = test_direct_connection()
    mavproxy_ok = test_mavproxy_connection()
    
    print("\n" + "=" * 50)
    if direct_ok and mavproxy_ok:
        print("🎉 SUCCESS: Both direct and MAVProxy connections working!")
        print("✅ Mission Planner should now show proximity data")
    elif direct_ok:
        print("⚠️  PARTIAL: LiDAR bridge working, but MAVProxy relay issue")
        print("💡 Check MAVProxy configuration and restart")
    else:
        print("❌ FAILED: No LiDAR data detected")
        print("💡 Check LiDAR connection and permissions")