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
    print("\nListening for DISTANCE_SENSOR messages...")
    print("Make sure combo_proximity_bridge_v9.py is running!\n")
    
    # Try to connect to Pixhawk
    candidates = ['/dev/ttyACM0'] + [f'/dev/ttyACM{i}' for i in range(1, 4)]
    mavlink = None
    
    for port in candidates:
        try:
            print(f"Trying {port}...")
            mavlink = mavutil.mavlink_connection(port, baud=57600)
            mavlink.wait_heartbeat(timeout=3)
            print(f"✓ Connected to Pixhawk at {port}")
            break
        except:
            continue
    
    if not mavlink:
        print("✗ Failed to connect to Pixhawk")
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

