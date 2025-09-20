import os
import sys
import time
from typing import Optional

from .config import load_config, save_config
from .hardware import detect_devices
from .updater import update_from_github
from .process_manager import ProcessManager
from .deps import ensure_dependencies


def run_cli_wizard(manifest_url: str, zip_url: str, base_dir_hint: Optional[str] = None):
    print("=== Astra Wizard (CLI) ===")
    cfg = load_config()
    print("Channel:", cfg.get("channel"))
    print("Step 1: Update scripts from GitHub…")
    target_dir = None
    try:
        if 'example.com' in manifest_url or 'example.com' in zip_url:
            raise RuntimeError("Update URLs not configured; using local fallback")
        target_dir = update_from_github(manifest_url, zip_url)
        print("Using scripts:", target_dir)
    except Exception as e:
        print(f"Update skipped: {e}")
        target_dir = base_dir_hint or os.getcwd()
        print("Using local scripts:", target_dir)

    print("Step 2: Detect hardware…")
    print("Ensuring dependencies…")
    if not ensure_dependencies():
        print("Some dependencies failed to install; continuing anyway.")
    
    dev = detect_devices()
    print("Devices:", dev)
    if dev.get("pixhawk"):
        cfg["pixhawk_port"] = dev["pixhawk"]
    if dev.get("lidar"):
        cfg["lidar_port"] = dev["lidar"]
    save_config(cfg)

    print("Step 3: Start components…")
    base_dir = base_dir_hint or target_dir
    pm = ProcessManager(base_dir)
    pm.start_proximity()
    pm.start_data_relay()

    print("Running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pm.stop_all()


