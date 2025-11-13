#!/usr/bin/env python3
"""
Test script to verify DISTANCE_SENSOR messages are being sent to Pixhawk
Run this while proximity bridge is running to verify messages are received
"""

import time
from pymavlink import mavutil

def test_receive_messages():
    """Listen for DISTANCE_SENSOR messages from proximity bridge"""
    print("=" * 60)
    print("Proximity Bridge MAVLink Message Test")
    print("=" * 60)
    print("\nNOTE: This script connects to Pixhawk via UDP (Mission Planner style)")
    print("If proximity bridge is already using /dev/ttyACM0, use Mission Planner instead")
    print("Or check /tmp/proximity_v9.json for sensor data\n")
    
    # Check if proximity bridge is running
    import os
    proximity_file = "/tmp/proximity_v9.json"
    if os.path.exists(proximity_file):
        try:
            import json
            with open(proximity_file, 'r') as f:
                data = json.load(f)
            print(f"✓ Proximity bridge is running (last update: {data.get('timestamp', 'unknown')})")
            print(f"  Sectors: {data.get('sectors_cm', [])}")
            print(f"  Messages sent: {data.get('messages_sent', 0)}")
        except Exception as e:
            print(f"⚠ Could not read proximity file: {e}")
    else:
        print("✗ Proximity bridge not running or not writing data")
        print("  Make sure combo_proximity_bridge_v9.py is running!")
        return
    
    # Try UDP connection (won't conflict with serial)
    print("\nTrying UDP connection (for Mission Planner style)...")
    try:
        # UDP works alongside the running proximity bridge; Mission Planner typically listens on the same port.
        mavlink = mavutil.mavlink_connection('udp:127.0.0.1:14550', input=False)
        print("✓ UDP connection ready (but may not receive serial messages)")
        print("  Use Mission Planner to check for DISTANCE_SENSOR messages")
        return
    except:
        pass
    
    # Try to connect to Pixhawk via serial (may conflict if proximity bridge is using it)
    # This is a fallback for standalone testing; it will fail politely if the main bridge already owns the port.
    candidates = ['/dev/ttyACM0'] + [f'/dev/ttyACM{i}' for i in range(1, 4)]
    mavlink = None
    
    for port in candidates:
        try:
            print(f"\nTrying {port}...")
            mavlink = mavutil.mavlink_connection(port, baud=57600)
            mavlink.wait_heartbeat(timeout=3)
            print(f"✓ Connected to Pixhawk at {port}")
            break
        except Exception as e:
            if "multiple access" in str(e).lower() or "device" in str(e).lower():
                print(f"  ⚠ Port in use (proximity bridge likely using it): {e}")
                print("  → Use Mission Planner to check for DISTANCE_SENSOR messages instead")
                return
            continue
    
    if not mavlink:
        print("\n✗ Failed to connect to Pixhawk")
        print("  The proximity bridge may already be using the serial port")
        print("  Check Mission Planner → Ctrl-F → MAVLink Inspector for DISTANCE_SENSOR messages")
        return
    
    # Listen for messages
    sector_counts = {}
    start_time = time.time()
    last_summary = time.time()
    
    print("\nListening for DISTANCE_SENSOR messages (Press Ctrl+C to stop)...\n")
    
    try:
        while True:
            msg = mavlink.recv_match(blocking=False, timeout=0.1)
            
            if msg and msg.get_type() == 'DISTANCE_SENSOR':
                # Count messages per sector
                sector_id = msg.id
                if sector_id not in sector_counts:
                    sector_counts[sector_id] = 0
                sector_counts[sector_id] += 1
                
                # Print sample message details
                print(f"[DISTANCE_SENSOR] Sector {sector_id}: "
                      f"distance={msg.current_distance}cm, "
                      f"orientation={msg.orientation}, "
                      f"type={msg.type}, "
                      f"id={msg.id}")
            
            # Print summary every 5 seconds
            # This gives a quick sanity check without waiting for the script to finish.
            if time.time() - last_summary > 5.0:
                elapsed = time.time() - start_time
                print(f"\n--- Summary (after {elapsed:.1f}s) ---")
                if sector_counts:
                    for sector_id in sorted(sector_counts.keys()):
                        count = sector_counts[sector_id]
                        rate = count / elapsed
                        print(f"  Sector {sector_id}: {count} messages ({rate:.1f}/s)")
                else:
                    print("  ✗ NO DISTANCE_SENSOR messages received!")
                    print("  Check that combo_proximity_bridge_v9.py is running")
                print()
                last_summary = time.time()
                
    except KeyboardInterrupt:
        print("\n\nStopped listening")
        
        # Final summary
        elapsed = time.time() - start_time
        print(f"\n--- Final Summary ({elapsed:.1f}s total) ---")
        if sector_counts:
            for sector_id in sorted(sector_counts.keys()):
                count = sector_counts[sector_id]
                rate = count / elapsed
                print(f"  Sector {sector_id}: {count} messages ({rate:.1f}/s)")
        else:
            print("  ✗ NO DISTANCE_SENSOR messages received!")
            print("\n  Troubleshooting:")
            print("  1. Check combo_proximity_bridge_v9.py is running")
            print("  2. Check MAVLink connection is working")
            print("  3. Check for errors in proximity bridge output")

if __name__ == "__main__":
    test_receive_messages()

