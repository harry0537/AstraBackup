#!/usr/bin/env python3
"""
Project Astra NZ - Data Relay V9 (Component 197)
Relays telemetry and images to AWS dashboard every minute - Bug Fixes from V7
"""

import time
import json
import base64
import requests
import threading
from datetime import datetime
from pymavlink import mavutil
import os
from PIL import Image
import io

# Configuration - matches working proximity bridge
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600
DASHBOARD_IP = os.environ.get('ASTRA_DASHBOARD_IP', "10.244.77.186")
DASHBOARD_PORT = int(os.environ.get('ASTRA_DASHBOARD_PORT', "8081"))
COMPONENT_ID = 197

# Load config if available
try:
    config_json = os.environ.get('ASTRA_CONFIG')
    if config_json:
        config = json.loads(config_json)
        DASHBOARD_IP = config.get('dashboard_ip', DASHBOARD_IP)
        DASHBOARD_PORT = config.get('dashboard_port', DASHBOARD_PORT)
except:
    pass

class DataRelay:
    def __init__(self):
        self.mavlink = None
        self.running = True
        self.dashboard_url = f"http://{DASHBOARD_IP}:{DASHBOARD_PORT}"

        # Telemetry data
        self.telemetry = {
            'timestamp': None,
            'gps': {'lat': 0, 'lon': 0, 'alt': 0, 'fix': 0},
            'attitude': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'battery': {'voltage': 0, 'current': 0, 'remaining': 0},
            'proximity': {},
            'status': 'INITIALIZING'
        }

        # Image tracking
        self.last_image_send = 0
        self.images_sent = 0
        # We act as the courier: pull fresh telemetry from the Pixhawk, scoop up the latest crop photo,
        # and push both to the web dashboard on a predictable cadence.

    def connect_pixhawk(self):
        """Connect to Pixhawk for telemetry - Try UDP first to avoid serial conflicts"""
        try:
            # Try UDP first (if proximity bridge is using serial)
            # This allows both components to run simultaneously
            # UDP lets multiple clients subscribe without fighting over the USB cable.
            try:
                print("Attempting UDP connection to Pixhawk (udp:127.0.0.1:14550)...")
                self.mavlink = mavutil.mavlink_connection(
                    'udp:127.0.0.1:14550',
                    source_system=255,
                    source_component=COMPONENT_ID
                )
                # For UDP, we don't wait for heartbeat as it might not be immediately available
                print("✓ Connected to Pixhawk via UDP (may need mavproxy or Mission Planner)")
                return True
            except Exception as e:
                print(f"  UDP failed: {e}, trying serial...")
                self.mavlink = None
            
            # Fallback to serial (only if UDP fails)
            candidates = [PIXHAWK_PORT] + [f'/dev/ttyACM{i}' for i in range(4)]

            for port in candidates:
                if not os.path.exists(port):
                    continue
                try:
                    print(f"Connecting to Pixhawk at {port}")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=255,
                        source_component=COMPONENT_ID
                    )
                    self.mavlink.wait_heartbeat(timeout=5)
                    print("✓ Connected to Pixhawk via serial")
                    return True
                except Exception as e:
                    print(f"  Serial {port} failed: {e}")
                    self.mavlink = None

            print("⚠ Pixhawk not available (running in demo mode)")
            return False
        except Exception as e:
            print(f"✗ Pixhawk connection failed: {e}")
            return False

    def update_telemetry(self):
        """Update telemetry from MAVLink messages"""
        if not self.mavlink:
            return

        # Process multiple messages to catch all telemetry updates
        for _ in range(10):  # Process up to 10 messages per call
            # We poll quickly and bail when the queue runs dry to keep latency low.
            msg = self.mavlink.recv_match(blocking=False)
            if not msg:
                break

            msg_type = msg.get_type()

            if msg_type == 'GPS_RAW_INT':
                self.telemetry['gps']['lat'] = msg.lat / 1e7
                self.telemetry['gps']['lon'] = msg.lon / 1e7
                self.telemetry['gps']['alt'] = msg.alt / 1000
                self.telemetry['gps']['fix'] = msg.fix_type
                # Debug: Print GPS update occasionally
                if hasattr(self, '_last_gps_print'):
                    if time.time() - self._last_gps_print > 5.0:
                        print(f"\n[GPS] lat={self.telemetry['gps']['lat']:.7f}, lon={self.telemetry['gps']['lon']:.7f}, fix={self.telemetry['gps']['fix']}")
                        self._last_gps_print = time.time()
                else:
                    self._last_gps_print = time.time()

            elif msg_type == 'ATTITUDE':
                self.telemetry['attitude']['roll'] = msg.roll
                self.telemetry['attitude']['pitch'] = msg.pitch
                self.telemetry['attitude']['yaw'] = msg.yaw

            elif msg_type == 'SYS_STATUS':
                self.telemetry['battery']['voltage'] = msg.voltage_battery / 1000
                self.telemetry['battery']['current'] = msg.current_battery / 100
                self.telemetry['battery']['remaining'] = msg.battery_remaining

    def send_telemetry(self):
        """Send telemetry to dashboard"""
        self.telemetry['timestamp'] = datetime.now().isoformat()
        self.telemetry['status'] = 'OPERATIONAL'

        # Add proximity data
        try:
            # The proximity bridge writes its latest fusion results to disk, so we piggyback on that instead of subscribing again.
            with open('/tmp/proximity_v9.json', 'r') as f:
                prox = json.load(f)
            self.telemetry['proximity'] = {
                'sectors_cm': prox.get('sectors_cm', []),
                'min_cm': prox.get('min_cm', None),
                'timestamp': prox.get('timestamp', None)
            }
        except:
            pass

        try:
            response = requests.post(
                f"{self.dashboard_url}/telemetry",
                json=self.telemetry,
                timeout=2
            )
            if response.status_code == 200:
                # Debug: Log GPS data if available
                if self.telemetry.get('gps', {}).get('lat', 0) != 0:
                    gps = self.telemetry['gps']
                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Telemetry sent: GPS lat={gps['lat']:.7f}, lon={gps['lon']:.7f}, fix={gps['fix']}", end='', flush=True)
                return True
            else:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Telemetry send failed: HTTP {response.status_code}", end='', flush=True)
        except Exception as e:
            print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✗ Telemetry send error: {e}", end='', flush=True)
        return False

    def send_image(self):
        """Send image to dashboard"""
        image_path = "/tmp/crop_latest.jpg"

        if not os.path.exists(image_path):
            return False

        try:
            # Check file age (don't send stale images)
            # We do not want to blast the dashboard with the same photo if the crop monitor pauses.
            file_age = time.time() - os.path.getmtime(image_path)
            if file_age > 90:
                return False

            # Load and compress image
            with Image.open(image_path) as img:
                # FIX BUG #9: Use new Pillow API for resampling
                # Try new API first, fall back to old for compatibility
                try:
                    # Pillow 10.0+ uses Image.Resampling.LANCZOS
                    img.thumbnail((1024, 768), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Fallback for older Pillow versions
                    img.thumbnail((1024, 768), Image.LANCZOS)

                # Convert to JPEG with compression
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=75)
                image_bytes = buffer.getvalue()

            # Base64 encode
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            # Send to dashboard
            # The dashboard expects a JSON blob so we inline the image rather than juggling multipart uploads.
            payload = {
                'timestamp': datetime.now().isoformat(),
                'type': 'scheduled',
                'image': image_b64,
                'telemetry': self.telemetry
            }

            response = requests.post(
                f"{self.dashboard_url}/image",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                self.images_sent += 1
                self.last_image_send = time.time()
                return True
            else:
                return False

        except Exception as e:
            print(f"Image send error: {e}")
            return False

    def telemetry_thread(self):
        """Thread for telemetry updates"""
        last_send = time.time()

        while self.running:
            # Update from MAVLink
            self.update_telemetry()

            # Send every 2 seconds
            # A short period keeps the dashboard responsive without saturating the network.
            if time.time() - last_send > 2:
                self.send_telemetry()
                last_send = time.time()

            time.sleep(0.1)

    def image_thread(self):
        """Thread for image relay"""
        while self.running:
            # Send image every minute
            # We give the crop monitor a minute between uploads to avoid hammering slower networks.
            if time.time() - self.last_image_send >= 60:
                if self.send_image():
                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✓ Image sent to dashboard (#{self.images_sent})", end='')

            time.sleep(5)

    def print_status(self):
        """Print relay status"""
        uptime = int(time.time() - self.start_time)
        last_img = int(time.time() - self.last_image_send) if self.last_image_send > 0 else 0

        print(f"\r[{uptime:4d}s] Images sent: {self.images_sent:3d} | "
              f"Last: {last_img:3d}s ago | "
              f"Dashboard: {DASHBOARD_IP}:{DASHBOARD_PORT}", end='')

    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Data Relay V9 - Component 197")
        print(f"Dashboard: {self.dashboard_url}")
        print("=" * 60)

        self.start_time = time.time()

        # Connect to Pixhawk
        if not self.connect_pixhawk():
            print("Running in demo mode (no telemetry)")

        # Start threads
        # Run telemetry and image loops in the background so they can operate independently.
        telem_thread = threading.Thread(target=self.telemetry_thread, daemon=True)
        telem_thread.start()

        img_thread = threading.Thread(target=self.image_thread, daemon=True)
        img_thread.start()

        print("\n✓ Data relay operational")
        print("  • Telemetry: Every 2 seconds")
        print("  • Images: Every 60 seconds")
        print()

        # Keep running with status updates
        try:
            last_status = time.time()
            while self.running:
                if time.time() - last_status > 5:
                    self.print_status()
                    last_status = time.time()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutdown initiated...")
            self.running = False

if __name__ == "__main__":
    relay = DataRelay()
    relay.run()
