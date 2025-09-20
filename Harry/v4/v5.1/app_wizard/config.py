import json
import os
from typing import Any, Dict

DEFAULT_CONFIG = {
    "channel": "stable",
    "dashboard_ip": "10.244.77.186",
    "dashboard_port": 8081,
    "mavlink_port": 14550,
    "pixhawk_port": "/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00",
    "lidar_port": "/dev/ttyUSB0",
}

def config_path() -> str:
    root = os.path.expanduser("~/.astra")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "config_v5.json")

def load_config() -> Dict[str, Any]:
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    path = config_path()
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


