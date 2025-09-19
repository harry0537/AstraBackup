#!/usr/bin/env python3
"""
Project Astra NZ - Data Relay V5.1 (Component 197)
 - Configurable Pixhawk port via env or config.json
 - Reads proximity snapshot from /tmp/proximity_v4.json for now (backward-compatible)
"""

import os
import time
import json
import base64
import threading
from datetime import datetime
from pymavlink import mavutil
import requests
from PIL import Image
import io
import pathlib


def load_config():
    try:
        cfg_path = pathlib.Path(__file__).resolve().parent / 'config.json'
        if cfg_path.exists():
            with open(cfg_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


CONFIG = load_config()

DASHBOARD_IP = os.environ.get('ASTRA_DASHBOARD_IP', CONFIG.get('dashboard_ip', '10.244.77.186'))
DASHBOARD_PORT = int(os.environ.get('ASTRA_DASHBOARD_PORT', str(CONFIG.get('dashboard_port', 8081))))
PIXHAWK_PORT = os.environ.get('ASTRA_PIXHAWK_PORT', CONFIG.get('pixhawk_port', '/dev/pixhawk'))
PIXHAWK_BAUD = int(os.environ.get('ASTRA_PIXHAWK_BAUD', str(CONFIG.get('pixhawk_baud', 57600))))


class DataRelayV5:
    def __init__(self):
        self.mavlink = None
        self.running = True
        self.dashboard_url = f"http://{DASHBOARD_IP}:{DASHBOARD_PORT}"
        self.telemetry = {
            'timestamp': None,
            'gps': {'lat': 0, 'lon': 0, 'alt': 0, 'fix': 0},
            'attitude': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'battery': {'voltage': 0, 'current': 0, 'remaining': 0},
            'proximity': {},
            'status': 'INITIALIZING'
        }
        self.image_queue = []
        self.last_daily_check = datetime.now().date()
        self.daily_sent = False
        self.request_reset = datetime.now()
        self.request_count = 0

    def connect_pixhawk(self):
        try:
            candidates = [PIXHAWK_PORT,
                          '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00']
            candidates += [f'/dev/ttyACM{i}' for i in range(4)]
            last_error = None
            for port in candidates:
                try:
                    print(f"[Relay] Connecting to Pixhawk at {port}")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=255,
                        source_component=197
                    )
                    self.mavlink.wait_heartbeat(timeout=5)
                    print("[Relay] ✓ Connected to Pixhawk")
                    return True
                except Exception as e:
                    last_error = e
                    self.mavlink = None
            print(f"[Relay] ✗ Pixhawk connection failed: {last_error}")
            return False
        except Exception as e:
            print(f"[Relay] ✗ Pixhawk connection failed: {e}")
            return False

    def update_telemetry_from_mav(self):
        if not self.mavlink:
            return
        msg = self.mavlink.recv_match(blocking=False)
        if not msg:
            return
        t = msg.get_type()
        if t == 'GPS_RAW_INT':
            self.telemetry['gps']['lat'] = msg.lat / 1e7
            self.telemetry['gps']['lon'] = msg.lon / 1e7
            self.telemetry['gps']['alt'] = msg.alt / 1000
            self.telemetry['gps']['fix'] = msg.fix_type
        elif t == 'ATTITUDE':
            self.telemetry['attitude']['roll'] = msg.roll
            self.telemetry['attitude']['pitch'] = msg.pitch
            self.telemetry['attitude']['yaw'] = msg.yaw
        elif t == 'SYS_STATUS':
            self.telemetry['battery']['voltage'] = msg.voltage_battery / 1000
            self.telemetry['battery']['current'] = msg.current_battery / 100
            self.telemetry['battery']['remaining'] = msg.battery_remaining
        elif t == 'DISTANCE_SENSOR':
            sector = int((msg.orientation % 360) / 45)
            self.telemetry['proximity'][f'sector_{sector}'] = msg.current_distance / 100

    def enrich_proximity_snapshot(self):
        try:
            with open('/tmp/proximity_v4.json', 'r') as f:
                prox = json.load(f)
            self.telemetry['proximity'] = {
                'sectors_cm': prox.get('sectors_cm', []),
                'min_cm': prox.get('min_cm', None),
                'ts': prox.get('timestamp', None)
            }
        except Exception:
            pass

    def send_telemetry(self):
        self.telemetry['timestamp'] = datetime.now().isoformat()
        self.telemetry['status'] = 'OPERATIONAL'
        self.enrich_proximity_snapshot()
        try:
            requests.post(f"{self.dashboard_url}/telemetry", json=self.telemetry, timeout=2)
        except Exception:
            pass

    def telemetry_loop(self):
        last_send = time.time()
        while self.running:
            self.update_telemetry_from_mav()
            if time.time() - last_send > 2:
                self.send_telemetry()
                last_send = time.time()
            time.sleep(0.1)

    def check_daily_image(self):
        now = datetime.now()
        if now.date() != self.last_daily_check:
            self.last_daily_check = now.date()
            self.daily_sent = False
        if now.hour == 12 and not self.daily_sent:
            self.capture_and_queue_image('scheduled')
            self.daily_sent = True

    def capture_and_queue_image(self, trigger_type):
        image_path = '/tmp/crop_latest.jpg'
        if not os.path.exists(image_path):
            try:
                from PIL import Image, ImageDraw
                img = Image.new('RGB', (640, 480), color='green')
                draw = ImageDraw.Draw(img)
                draw.text((10, 10), f"Test Image - {datetime.now()}", fill='white')
                img.save(image_path, quality=70)
            except Exception:
                return
        self.image_queue.append({'path': image_path, 'type': trigger_type, 'timestamp': datetime.now().isoformat()})

    def send_queued_images(self):
        if not self.image_queue:
            return
        for data in self.image_queue[:]:
            if self.send_image(data):
                try:
                    self.image_queue.remove(data)
                except ValueError:
                    pass

    def send_image(self, image_data):
        try:
            with Image.open(image_data['path']) as img:
                img.thumbnail((1024, 768))
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=75)
                image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            payload = {
                'timestamp': image_data['timestamp'],
                'type': image_data['type'],
                'image': image_b64,
                'telemetry': self.telemetry
            }
            r = requests.post(f"{self.dashboard_url}/image", json=payload, timeout=10)
            if r.status_code == 200:
                print("[Relay] ✓ Image sent")
                return True
        except Exception:
            pass
        print("[Relay] ✗ Image send failed")
        return False

    def image_loop(self):
        while self.running:
            self.check_daily_image()
            self.send_queued_images()
            time.sleep(10)

    def run(self):
        print("=" * 50)
        print("Data Relay V5.1 - Component 197")
        print(f"Dashboard: {self.dashboard_url}")
        print("=" * 50)

        if not self.connect_pixhawk():
            print("[Relay] Running in demo mode (no Pixhawk)")

        t1 = threading.Thread(target=self.telemetry_loop, daemon=True)
        t1.start()
        t2 = threading.Thread(target=self.image_loop, daemon=True)
        t2.start()

        print("[Relay] ✓ Operational")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False


if __name__ == '__main__':
    DataRelayV5().run()


