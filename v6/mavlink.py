#!/usr/bin/env python3
"""
Fix ArduPilot parameters for obstacle avoidance
"""
from pymavlink import mavutil
import time

def set_avoidance_params(connection_string='/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'):
    print("Connecting to Pixhawk...")
    master = mavutil.mavlink_connection(connection_string, baud=57600)
    master.wait_heartbeat()
    print("Connected!")
    
    # Parameters to set for obstacle avoidance
    params = {
        'AVOID_ENABLE': 7,      # All avoidance types
        'OA_TYPE': 1,           # Bendy Ruler
        'OA_BR_LOOKAHEAD': 5,   # 5 meter lookahead
        'AVOID_MARGIN': 2,      # 2 meter margin
        'PRX1_TYPE': 2,         # MAVLink proximity
        'PRX_LOG': 1,           # Log proximity data
    }
    
    print("\nSetting avoidance parameters:")
    for param, value in params.items():
        print(f"  {param} = {value}")
        master.mav.param_set_send(
            master.target_system, master.target_component,
            param.encode('utf-8'),
            value,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        time.sleep(0.1)
    
    print("\nParameters set! Please reboot Pixhawk for changes to take effect.")
    print("In Mission Planner: Actions → Reboot Pixhawk")

if __name__ == "__main__":
    set_avoidance_params()