#!/usr/bin/env python3
"""
Proximity Launcher V5.1
- Keeps working_combo_proximity.py unchanged
- Injects detected ports into FixedComboProximityBridge instance before run()
"""

import os
import json
import sys
import pathlib


def load_config():
    """Load config.json from this directory if present."""
    try:
        here = pathlib.Path(__file__).resolve().parent
        cfg_path = here / 'config.json'
        if cfg_path.exists():
            with open(cfg_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def main():
    # Defer import so we don't affect the working script
    from working_combo_proximity import FixedComboProximityBridge

    config = load_config()

    # Prefer environment variables, then config.json, then class defaults
    lidar_port = os.environ.get('ASTRA_LIDAR_PORT') or config.get('lidar_port')
    pixhawk_port = os.environ.get('ASTRA_PIXHAWK_PORT') or config.get('pixhawk_port')

    bridge = FixedComboProximityBridge()

    if lidar_port:
        bridge.lidar_port = lidar_port
    if pixhawk_port:
        bridge.pixhawk_port = pixhawk_port

    print("Proximity Launcher V5.1")
    print(f"  LIDAR   port: {bridge.lidar_port}")
    print(f"  Pixhawk port: {bridge.pixhawk_port}")

    bridge.run()


if __name__ == "__main__":
    main()


