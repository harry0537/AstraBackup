#!/usr/bin/env python3
"""
Project Astra NZ - Parameter Application Tool
Applies .param file to Pixhawk via MAVLink
"""

import sys
import os
import time
import argparse
from pymavlink import mavutil

def load_param_file(param_file):
    """Load parameter file and return dict of {name: value}"""
    params = {}
    try:
        with open(param_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                # Parse "PARAM_NAME,VALUE" format
                # We keep the format intentionally simple so teammates can edit the file with any text editor.
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        param_name = parts[0].strip()
                        try:
                            param_value = float(parts[1].strip())
                            params[param_name] = param_value
                        except ValueError:
                            print(f"  ⚠ Skipping invalid value: {line}")
                            continue
        print(f"✓ Loaded {len(params)} parameters from {param_file}")
        return params
    except Exception as e:
        print(f"✗ Failed to load param file: {e}")
        return None

def apply_params(master, params, backup_file=None):
    """Apply parameters to Pixhawk"""
    print("\n=== Applying Parameters ===")
    
    # Wait for heartbeat
    print("Waiting for Pixhawk heartbeat...")
    master.wait_heartbeat(timeout=10)
    print("✓ Connected to Pixhawk")
    
    # Backup current parameters if requested
    if backup_file:
        print(f"\nBacking up current parameters to {backup_file}...")
        try:
            master.param_fetch_all()
            time.sleep(2)
            
            with open(backup_file, 'w') as f:
                f.write("# Pixhawk Parameter Backup\n")
                f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Wait for all params to be received
                params_received = {}
                timeout = time.time() + 10
                while time.time() < timeout:
                    msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
                    if msg:
                        params_received[msg.param_id] = msg.param_value
                
                # Write sorted parameters
                for param_name in sorted(params_received.keys()):
                    f.write(f"{param_name},{params_received[param_name]}\n")
            
            print(f"✓ Backup saved ({len(params_received)} parameters)")
        except Exception as e:
            print(f"⚠ Backup failed: {e}")
    
    # Apply parameters
    print(f"\nApplying {len(params)} parameters...")
    applied = 0
    failed = 0
    
    for param_name, param_value in params.items():
        # Push each parameter one at a time so we can report exactly which ones fail.
        try:
            # Send parameter set
            master.mav.param_set_send(
                master.target_system,
                master.target_component,
                param_name.encode('utf-8'),
                param_value,
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            
            # Wait for acknowledgment
            ack = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
            if ack and ack.param_id == param_name:
                if abs(ack.param_value - param_value) < 0.001:  # Float comparison
                    applied += 1
                    if applied % 10 == 0:
                        print(f"  Progress: {applied}/{len(params)}...")
                else:
                    print(f"  ⚠ {param_name}: Set to {param_value}, but readback is {ack.param_value}")
                    failed += 1
            else:
                print(f"  ⚠ {param_name}: No acknowledgment received")
                failed += 1
            
            time.sleep(0.05)  # Small delay between params
            
        except Exception as e:
            print(f"  ✗ {param_name}: {e}")
            failed += 1
    
    print(f"\n=== Results ===")
    print(f"✓ Applied: {applied}")
    if failed > 0:
        print(f"✗ Failed: {failed}")
    
    return applied, failed

def main():
    parser = argparse.ArgumentParser(description='Apply .param file to Pixhawk')
    parser.add_argument('--port', '-p', default='/dev/ttyACM0',
                        help='Pixhawk serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baud', '-b', type=int, default=57600,
                        help='Serial baud rate (default: 57600)')
    parser.add_argument('--file', '-f', required=True,
                        help='.param file to apply')
    parser.add_argument('--backup', '-B',
                        help='Backup current parameters to this file before applying')
    parser.add_argument('--reboot', '-r', action='store_true',
                        help='Reboot Pixhawk after applying parameters')
    
    args = parser.parse_args()
    
    # Load parameter file
    if not os.path.exists(args.file):
        print(f"✗ Parameter file not found: {args.file}")
        sys.exit(1)
    
    params = load_param_file(args.file)
    if params is None:
        sys.exit(1)
    
    # Connect to Pixhawk
    print(f"\nConnecting to Pixhawk at {args.port} ({args.baud} baud)...")
    try:
        master = mavutil.mavlink_connection(args.port, baud=args.baud)
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        print("  Check that Pixhawk is connected and port is correct")
        sys.exit(1)
    
    # Apply parameters
    applied, failed = apply_params(master, params, args.backup)
    
    # Reboot if requested
    if args.reboot:
        print("\nRebooting Pixhawk...")
        try:
            master.reboot_autopilot()
            print("✓ Reboot command sent")
            print("  Pixhawk will restart in a few seconds")
        except Exception as e:
            print(f"✗ Reboot failed: {e}")
    
    if failed == 0:
        print("\n✓ All parameters applied successfully!")
        if not args.reboot:
            print("  Remember to reboot Pixhawk for changes to take effect")
    else:
        print(f"\n⚠ {failed} parameters failed to apply. Check connection and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()

