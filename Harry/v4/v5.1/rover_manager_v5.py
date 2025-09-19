#!/usr/bin/env python3
"""
Rover Manager V5.1
- Detects Pixhawk, RPLidar, and optional RealSense ports
- Writes config.json for launchers
- Launches proximity first, then data relay
"""

import os
import sys
import json
import time
import subprocess
import pathlib


def detect_ports():
    """Detect likely ports for Pixhawk and LiDAR.
    This is Linux-focused; on Windows WSL/WSA environments, user may override via env.
    """
    candidates = {
        'pixhawk': [
            '/dev/pixhawk',
            '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00',
        ] + [f'/dev/ttyACM{i}' for i in range(4)],
        'lidar': [
            '/dev/rplidar',
            '/dev/ttyUSB0',
            '/dev/ttyUSB1',
        ],
    }

    detected = {
        'pixhawk_port': None,
        'lidar_port': None,
    }

    for port in candidates['pixhawk']:
        if os.path.exists(port):
            detected['pixhawk_port'] = port
            break
    for port in candidates['lidar']:
        if os.path.exists(port):
            detected['lidar_port'] = port
            break

    # Allow env overrides
    detected['pixhawk_port'] = os.environ.get('ASTRA_PIXHAWK_PORT', detected['pixhawk_port'])
    detected['lidar_port'] = os.environ.get('ASTRA_LIDAR_PORT', detected['lidar_port'])
    return detected


def write_config(cfg: dict, dir_path: pathlib.Path):
    cfg_path = dir_path / 'config.json'
    try:
        with open(cfg_path, 'w') as f:
            json.dump(cfg, f, indent=2)
        print(f"[Manager] Wrote {cfg_path}")
    except Exception as e:
        print(f"[Manager] Failed to write config: {e}")


def launch_proximity(dir_path: pathlib.Path, env: dict):
    print("[Manager] Launching proximity...")
    cmd = [sys.executable, str(dir_path / 'proximity_launcher.py')]
    return subprocess.Popen(cmd, env=env)


def launch_relay(dir_path: pathlib.Path, env: dict):
    print("[Manager] Launching data relay...")
    cmd = [sys.executable, str(dir_path / 'rover_data_relay_v5.py')]
    return subprocess.Popen(cmd, env=env)


def main():
    here = pathlib.Path(__file__).resolve().parent
    detected = detect_ports()
    print("[Manager] Detected ports:")
    print(f"  Pixhawk: {detected['pixhawk_port']}")
    print(f"  LiDAR  : {detected['lidar_port']}")

    # Prepare config shared by proximity_launcher and relay
    cfg = {
        'pixhawk_port': detected['pixhawk_port'] or '/dev/pixhawk',
        'lidar_port': detected['lidar_port'] or '/dev/ttyUSB0',
        'dashboard_ip': os.environ.get('ASTRA_DASHBOARD_IP', '10.244.77.186'),
        'dashboard_port': int(os.environ.get('ASTRA_DASHBOARD_PORT', '8081')),
        'pixhawk_baud': int(os.environ.get('ASTRA_PIXHAWK_BAUD', '57600')),
    }
    write_config(cfg, here)

    # Base env with overrides, so scripts can read env directly as well
    env = os.environ.copy()
    if cfg['pixhawk_port']:
        env['ASTRA_PIXHAWK_PORT'] = cfg['pixhawk_port']
    if cfg['lidar_port']:
        env['ASTRA_LIDAR_PORT'] = cfg['lidar_port']
    env['ASTRA_DASHBOARD_IP'] = str(cfg['dashboard_ip'])
    env['ASTRA_DASHBOARD_PORT'] = str(cfg['dashboard_port'])
    env['ASTRA_PIXHAWK_BAUD'] = str(cfg['pixhawk_baud'])

    # Launch proximity first
    prox_proc = launch_proximity(here, env)
    time.sleep(3)

    # Then launch data relay
    relay_proc = launch_relay(here, env)

    print("[Manager] Both processes started. Press Ctrl+C to stop.")
    try:
        while True:
            # If any process exits, break
            ret_p = prox_proc.poll()
            ret_r = relay_proc.poll()
            if ret_p is not None:
                print(f"[Manager] Proximity exited with code {ret_p}")
                break
            if ret_r is not None:
                print(f"[Manager] Relay exited with code {ret_r}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Manager] Stopping...")
    finally:
        for proc in (prox_proc, relay_proc):
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass


if __name__ == '__main__':
    main()


