#!/usr/bin/env python3
"""
Project Astra NZ - Proximity Starter V4
- Verifies dependencies (pip install if missing)
- Ensures device access
- Starts working proximity bridge and data relay side-by-side
"""

import os
import sys
import subprocess
import time


def ensure_package(pkg_name: str, import_name: str = None):
    mod = import_name or pkg_name
    try:
        __import__(mod)
        return True
    except Exception:
        print(f"Installing missing package: {pkg_name}...")
        cmd = [sys.executable, '-m', 'pip', 'install', pkg_name]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            try:
                __import__(mod)
                return True
            except Exception:
                return False
        return False


def ensure_dependencies():
    ok = True
    ok &= ensure_package('rplidar-roboticia', 'rplidar')
    ok &= ensure_package('pymavlink')
    ok &= ensure_package('numpy')
    # RealSense optional
    try:
        __import__('pyrealsense2')
    except Exception:
        pass
    return ok


def ensure_devices():
    # Create friendly symlinks if the raw devices exist
    try:
        for idx in range(4):
            path = f'/dev/ttyUSB{idx}'
            if os.path.exists(path) and not os.path.exists('/dev/rplidar'):
                os.system(f'sudo ln -sf {path} /dev/rplidar')
                os.system(f'sudo chmod a+rw {path}')
                break
    except Exception:
        pass

    try:
        for idx in range(4):
            path = f'/dev/ttyACM{idx}'
            if os.path.exists(path) and not os.path.exists('/dev/pixhawk'):
                os.system(f'sudo ln -sf {path} /dev/pixhawk')
                os.system(f'sudo chmod a+rw {path}')
                break
    except Exception:
        pass


def start_processes():
    procs = []
    # Start working proximity bridge
    procs.append(subprocess.Popen([sys.executable, 'combo_proximity_bridge_v4.py']))
    time.sleep(1)
    # Start data relay (non-blocking)
    procs.append(subprocess.Popen([sys.executable, 'rover_data_relay_v4.py']))
    return procs


def main():
    print("=== Proximity Starter V4 ===")
    if not ensure_dependencies():
        print("Dependencies failed to install. Exiting.")
        sys.exit(1)

    ensure_devices()
    procs = start_processes()
    print("Started proximity bridge and data relay.")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == '__main__':
    main()


