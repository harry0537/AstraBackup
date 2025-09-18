#!/usr/bin/env python3
"""
Project Astra NZ - Data Relay V4 (Component 197)
Relays telemetry and images to AWS dashboard
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

# Configuration (reads from environment or uses defaults)
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600
DASHBOARD_IP = os.environ.get('ASTRA_DASHBOARD_IP', "10.244.77.186")
DASHBOARD_PORT = int(os.environ.get('ASTRA_DASHBOARD_PORT', "8081"))
COMPONENT_ID = 197

# Load full config if available
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
        
        # Image relay config
        self.daily_sent = False
        self.last_daily_check = datetime.now().date()
        self.request_count = 0
        self.request_reset = datetime.now()
        self.image_queue = []
        
        # Telemetry data
        self.telemetry = {
            'timestamp': None,
            'gps': {'lat': 0, 'lon': 0, 'alt': 0, 'fix': 0},
            'attitude': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'battery': {'voltage': 0, 'current': 0, 'remaining': 0},
            'proximity': {},
            'status': 'INITIALIZING'
        }
        
    def connect_pixhawk(self):
        """Connect to Pixhawk for telemetry"""
        try:
            print(f"Connecting to Pixhawk at {PIXHAWK_PORT}")
            self.mavlink = mavutil.mavlink_connection(
                PIXHAWK_PORT,
                baud=PIXHAWK_BAUD,
                source_system=255,
                source_component=COMPONENT_ID
            )
            self.mavlink.wait_heartbeat(timeout=10)
            print("✓ Connected to Pixhawk")
            return True
        except Exception as e:
            print(f"✗ Pixhawk connection failed: {e}")
            return False
            
    def update_telemetry(self):
        """Update telemetry from MAVLink messages"""
        if not self.mavlink:
            return
            
        msg = self.mavlink.recv_match(blocking=False)
        if not msg:
            return
            
        msg_type = msg.get_type()
        
        if msg_type == 'GPS_RAW_INT':
            self.telemetry['gps']['lat'] = msg.lat / 1e7
            self.telemetry['gps']['lon'] = msg.lon / 1e7
            self.telemetry['gps']['alt'] = msg.alt / 1000
            self.telemetry['gps']['fix'] = msg.fix_type
            
        elif msg_type == 'ATTITUDE':
            self.telemetry['attitude']['roll'] = msg.roll
            self.telemetry['attitude']['pitch'] = msg.pitch
            self.telemetry['attitude']['yaw'] = msg.yaw
            
        elif msg_type == 'SYS_STATUS':
            self.telemetry['battery']['voltage'] = msg.voltage_battery / 1000
            self.telemetry['battery']['current'] = msg.current_battery / 100
            self.telemetry['battery']['remaining'] = msg.battery_remaining
            
        elif msg_type == 'DISTANCE_SENSOR':
            # Capture proximity data from Component 195
            sector = int((msg.orientation % 360) / 45)
            self.telemetry['proximity'][f'sector_{sector}'] = msg.current_distance / 100
            
    def send_telemetry(self):
        """Send telemetry to dashboard"""
        self.telemetry['timestamp'] = datetime.now().isoformat()
        self.telemetry['status'] = 'OPERATIONAL'
        
        try:
            response = requests.post(
                f"{self.dashboard_url}/telemetry",
                json=self.telemetry,
                timeout=2
            )
            if response.status_code != 200:
                print(f"Dashboard telemetry error: {response.status_code}")
        except Exception as e:
            # Silent fail - don't flood console
            pass
            
    def check_daily_image(self):
        """Check if daily image should be sent"""
        now = datetime.now()
        
        # Reset daily flag at midnight
        if now.date() != self.last_daily_check:
            self.daily_sent = False
            self.last_daily_check = now.date()
            
        # Send at noon if not sent yet
        if now.hour == 12 and not self.daily_sent:
            print("Triggering daily image capture")
            self.capture_and_queue_image("scheduled")
            self.daily_sent = True
            
    def check_dashboard_commands(self):
        """Check for commands from dashboard"""
        try:
            response = requests.get(
                f"{self.dashboard_url}/commands",
                timeout=1
            )
            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    self.process_command(cmd)
        except:
            pass
            
    def process_command(self, cmd):
        """Process command from dashboard"""
        if cmd.get('type') == 'capture_image':
            # Check rate limit
            now = datetime.now()
            if (now - self.request_reset).seconds > 3600:
                self.request_count = 0
                self.request_reset = now
                
            if self.request_count < 5:
                print("Dashboard requested image capture")
                self.capture_and_queue_image("requested")
                self.request_count += 1
            else:
                print("Image request rate limit reached")
                
    def capture_and_queue_image(self, trigger_type):
        """Trigger image capture from Component 198"""
        image_path = "/tmp/crop_latest.jpg"
        
        # Trigger Component 198 capture (simplified for demo)
        # In production, use proper IPC mechanism
        if os.path.exists("crop_monitoring_system.py"):
            os.system(f"echo 'capture' > /tmp/crop_trigger")
            time.sleep(3)  # Wait for capture
            
        # Check if image exists
        if os.path.exists(image_path):
            self.image_queue.append({
                'path': image_path,
                'type': trigger_type,
                'timestamp': datetime.now().isoformat()
            })
            print(f"Image queued for transmission ({trigger_type})")
        else:
            # Use test image if no crop monitoring running
            self.create_test_image(image_path)
            self.image_queue.append({
                'path': image_path,
                'type': trigger_type,
                'timestamp': datetime.now().isoformat()
            })
            
    def create_test_image(self, path):
        """Create test image when crop monitoring not available"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (640, 480), color='green')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), f"Test Image - {datetime.now()}", fill='white')
        img.save(path, quality=70)
        
    def send_queued_images(self):
        """Send any queued images to dashboard"""
        if not self.image_queue:
            return
            
        for image_data in self.image_queue[:]:
            if self.send_image(image_data):
                self.image_queue.remove(image_data)
                
    def send_image(self, image_data):
        """Compress and send image to dashboard"""
        try:
            # Load and compress image
            with Image.open(image_data['path']) as img:
                # Resize for bandwidth
                img.thumbnail((1024, 768), Image.LANCZOS)
                
                # Convert to JPEG with compression
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=75)
                image_bytes = buffer.getvalue()
                
            # Base64 encode
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Send to dashboard
            payload = {
                'timestamp': image_data['timestamp'],
                'type': image_data['type'],
                'image': image_b64,
                'telemetry': self.telemetry
            }
            
            response = requests.post(
                f"{self.dashboard_url}/image",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✓ Image sent to dashboard ({image_data['type']})")
                return True
            else:
                print(f"✗ Image send failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Image send error: {e}")
            return False
            
    def telemetry_thread(self):
        """Thread for telemetry updates"""
        last_send = time.time()
        
        while self.running:
            # Update from MAVLink
            self.update_telemetry()
            
            # Send every 2 seconds
            if time.time() - last_send > 2:
                self.send_telemetry()
                last_send = time.time()
                
            time.sleep(0.1)
            
    def image_thread(self):
        """Thread for image management"""
        while self.running:
            # Check daily schedule
            self.check_daily_image()
            
            # Check dashboard commands
            self.check_dashboard_commands()
            
            # Send queued images
            self.send_queued_images()
            
            time.sleep(10)  # Check every 10 seconds
            
    def run(self):
        """Main execution"""
        print("=" * 50)
        print("Data Relay V4 - Component 197")
        print(f"Dashboard: {self.dashboard_url}")
        print("=" * 50)
        
        # Connect to Pixhawk
        if not self.connect_pixhawk():
            print("Running in demo mode (no Pixhawk)")
            
        # Start threads
        telem_thread = threading.Thread(target=self.telemetry_thread)
        telem_thread.daemon = True
        telem_thread.start()
        
        img_thread = threading.Thread(target=self.image_thread)
        img_thread.daemon = True
        img_thread.start()
        
        print("✓ Data relay operational")
        print("  • Telemetry: Every 2 seconds")
        print("  • Daily image: 12:00 PM")
        print("  • On-demand: Via dashboard")
        
        # Keep running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down data relay...")
            self.running = False

if __name__ == "__main__":
    relay = DataRelay()
    relay.run()