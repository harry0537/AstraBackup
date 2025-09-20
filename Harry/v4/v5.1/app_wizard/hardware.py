import os
import sys
import time
from typing import Dict


def detect_devices() -> Dict[str, str]:
    devices = {"pixhawk": "", "lidar": "", "realsense": "unknown"}
    # Linux paths
    candidates_usb = [f"/dev/ttyUSB{i}" for i in range(6)]
    candidates_acm = [f"/dev/ttyACM{i}" for i in range(6)]

    if os.name != 'nt':
        for p in ["/dev/rplidar"] + candidates_usb:
            if os.path.exists(p):
                devices["lidar"] = p
                break
        for p in ["/dev/pixhawk"] + candidates_acm:
            if os.path.exists(p):
                devices["pixhawk"] = p
                break
        try:
            import pyrealsense2 as rs  # noqa
            devices["realsense"] = "present"
        except Exception:
            devices["realsense"] = "missing"
    else:
        # Windows: COM ports
        try:
            import serial.tools.list_ports  # type: ignore
            ports = list(serial.tools.list_ports.comports())
            for port in ports:
                name = (port.description or "").lower()
                if "pixhawk" in name or "stm" in name:
                    devices["pixhawk"] = port.device
                if "silicon" in name or "usb serial" in name:
                    devices["lidar"] = port.device
        except Exception:
            pass
        try:
            import pyrealsense2 as rs  # noqa
            devices["realsense"] = "present"
        except Exception:
            devices["realsense"] = "missing"

    return devices


