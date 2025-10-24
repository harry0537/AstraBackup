#!/usr/bin/env python3
"""
Project Astra NZ - Web Telemetry Dashboard V8
Real-time monitoring interface for proximity sensors and system status - Bug Fixes from V7
"""

import json
import time
import threading
import os
from datetime import datetime
from flask import Flask, render_template_string, jsonify
import numpy as np

# FIX BUG #11: Add try/except for optional flask-cors dependency
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("[WARNING] flask-cors not installed - CORS disabled")

# Try to import sensor libraries (optional for dashboard)
try:
    from rplidar import RPLidar
    RPLIDAR_AVAILABLE = True
except ImportError:
    RPLIDAR_AVAILABLE = False

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

app = Flask(__name__)
if CORS_AVAILABLE:
    CORS(app)

# Global telemetry data
telemetry_data = {
    'proximity': [2500] * 8,  # 8 sectors in cm
    'system_status': {
        'proximity_bridge': 'Unknown',
        'data_relay': 'Unknown',
        'crop_monitor': 'Unknown'
    },
    'sensor_health': {
        'rplidar': 'Unknown',
        'realsense': 'Unknown',
        'pixhawk': 'Unknown'
    },
    'statistics': {
        'uptime': 0,
        'messages_sent': 0,
        'last_update': '',
        'rplidar_success_rate': 0,
        'realsense_fps': 0
    }
}

# HTML template for dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Project Astra NZ - Telemetry Dashboard V8</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid #00ff00;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 24px;
            text-shadow: 0 0 10px #00ff00;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .rover-vision-container {
            grid-column: 1 / -1;
            margin-top: 20px;
        }
        .vision-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        .proximity-panel {
            grid-column: 1;
        }
        .rover-vision-panel {
            grid-column: 2;
        }
        .proximity-panel .radar-container {
            width: 100%;
            height: 400px;
        }
        .proximity-panel .radar {
            width: 100%;
            height: 100%;
        }
        .panel {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 20px rgba(0,255,0,0.1);
        }
        .panel h2 {
            font-size: 16px;
            margin-bottom: 10px;
            color: #00ff00;
            text-shadow: 0 0 5px #00ff00;
        }
        .radar-container {
            position: relative;
            width: 280px;
            height: 280px;
            margin: 0 auto;
        }
        .radar {
            width: 100%;
            height: 100%;
        }
        .status-grid {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 10px;
            font-size: 14px;
        }
        .status-label {
            color: #888;
        }
        .status-value {
            text-align: right;
        }
        .status-ok { color: #00ff00; }
        .status-warning { color: #ffff00; }
        .status-error { color: #ff0000; }
        .proximity-values {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        .proximity-item {
            text-align: center;
            padding: 5px;
            background: #2a2a2a;
            border-radius: 3px;
        }
        .proximity-label {
            font-size: 10px;
            color: #888;
        }
        .proximity-value {
            font-size: 16px;
            font-weight: bold;
        }
        .safe { color: #00ff00; }
        .warning { color: #ffff00; }
        .danger { color: #ff0000; }
        .crop-image-container {
            text-align: center;
            margin-top: 10px;
        }
        .crop-image-container img {
            max-width: 100%;
            height: auto;
            max-height: 500px;
            border: 2px solid #00ff00;
            border-radius: 8px;
            box-shadow: 0 0 20px rgba(0,255,0,0.5);
            transition: all 0.3s ease;
        }
        .crop-image-container img:hover {
            box-shadow: 0 0 30px rgba(0,255,0,0.8);
            transform: scale(1.02);
        }
        .crop-status {
            margin-top: 15px;
            font-size: 14px;
            color: #888;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .rover-vision-container .panel {
            padding: 25px;
        }
        .rover-vision-container h2 {
            font-size: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>PROJECT ASTRA NZ - TELEMETRY DASHBOARD V8</h1>
        <p id="timestamp">--:--:--</p>
    </div>

    <div class="container">
        <div class="panel">
            <h2>SYSTEM STATUS</h2>
            <div class="status-grid" id="system-status">
                <!-- Populated by JavaScript -->
            </div>
        </div>

        <div class="panel">
            <h2>SENSOR HEALTH</h2>
            <div class="status-grid" id="sensor-health">
                <!-- Populated by JavaScript -->
            </div>
        </div>

        <div class="panel">
            <h2>STATISTICS</h2>
            <div class="status-grid" id="statistics">
                <!-- Populated by JavaScript -->
            </div>
        </div>
    </div>

    <div class="vision-row">
        <div class="proximity-panel">
            <div class="panel">
                <h2>PROXIMITY RADAR</h2>
                <div class="radar-container">
                    <canvas id="radar" class="radar"></canvas>
                </div>
                <div class="proximity-values" id="proximity-values">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
        </div>

        <div class="rover-vision-panel">
            <div class="panel">
                <h2>REAL-TIME ROVER VISION</h2>
                <div class="crop-image-container">
                    <img id="rover-vision" src="/api/crop/image" alt="Rover Vision" 
                         style="max-width: 100%; height: auto; border: 1px solid #00ff00;"
                         onerror="this.style.display='none'; document.getElementById('vision-offline').style.display='block';"
                         onload="this.style.display='block'; document.getElementById('vision-offline').style.display='none';">
                    <div id="vision-offline" style="display: none; padding: 20px; text-align: center; color: #ff6600;">
                        Rover vision offline - Crop monitor not running
                    </div>
                    <div class="crop-status" id="crop-status">
                        Rover vision updates every 5 seconds
                        <br><small><a href="/api/crop/status" target="_blank" style="color: #0ff;">Debug: Check crop status</a></small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Reliable refresh with proper error handling
        const roverVisionImg = document.getElementById('rover-vision');
        
        function refreshRoverVision() {
            const timestamp = new Date().getTime();
            const newSrc = `/api/crop/image?t=${timestamp}`;
            
            // Only update if the src is different
            if (roverVisionImg.src !== newSrc) {
                roverVisionImg.src = newSrc;
                console.log(`Refreshing rover vision at ${new Date().toLocaleTimeString()}`);
            }
        }
        
        // Handle image load errors
        roverVisionImg.onerror = function() {
            console.log('Rover vision image failed to load');
            // Try again in 2 seconds
            setTimeout(refreshRoverVision, 2000);
        };
        
        // Handle successful image load
        roverVisionImg.onload = function() {
            console.log('Rover vision image loaded successfully');
        };
        
        // Initial load and set up refresh timer
        refreshRoverVision();
        setInterval(refreshRoverVision, 5000); // Refresh every 5 seconds
        
        const canvas = document.getElementById('radar');
        const ctx = canvas.getContext('2d');
        
        // Make radar bigger to fit the larger container
        function resizeRadar() {
            const container = canvas.parentElement;
            const size = Math.min(container.clientWidth - 40, container.clientHeight - 100);
            canvas.width = size;
            canvas.height = size;
        }
        
        // Initial resize
        resizeRadar();
        
        // Resize on window resize
        window.addEventListener('resize', resizeRadar);
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const maxRadius = Math.min(canvas.width, canvas.height) / 2 - 20;

        // Sector angles (45° each, starting from front)
        const sectorAngles = [
            -22.5, 22.5, 67.5, 112.5, 157.5, -157.5, -112.5, -67.5
        ];
        const sectorNames = [
            'FRONT', 'F-RIGHT', 'RIGHT', 'B-RIGHT',
            'BACK', 'B-LEFT', 'LEFT', 'F-LEFT'
        ];

        function drawRadar(distances) {
            // Update center and radius for current canvas size
            const currentCenterX = canvas.width / 2;
            const currentCenterY = canvas.height / 2;
            const currentMaxRadius = Math.min(canvas.width, canvas.height) / 2 - 20;
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw grid circles
            ctx.strokeStyle = '#003300';
            ctx.lineWidth = 1;
            for (let r = 0.25; r <= 1; r += 0.25) {
                ctx.beginPath();
                ctx.arc(currentCenterX, currentCenterY, currentMaxRadius * r, 0, Math.PI * 2);
                ctx.stroke();

                // Distance labels
                ctx.fillStyle = '#004400';
                ctx.font = '10px monospace';
                ctx.fillText(`${Math.round(r * 25)}m`, currentCenterX + 5, currentCenterY - currentMaxRadius * r + 10);
            }

            // Draw sector lines
            for (let angle of sectorAngles) {
                const rad = (angle - 90) * Math.PI / 180;
                ctx.beginPath();
                ctx.moveTo(currentCenterX, currentCenterY);
                ctx.lineTo(
                    currentCenterX + currentMaxRadius * Math.cos(rad),
                    currentCenterY + currentMaxRadius * Math.sin(rad)
                );
                ctx.stroke();
            }

            // Draw obstacles
            for (let i = 0; i < 8; i++) {
                const distance = distances[i] / 100; // Convert to meters
                const normalizedDist = Math.min(distance / 25, 1); // Normalize to 25m max
                const pixelDist = normalizedDist * currentMaxRadius;

                // Calculate sector center angle
                const startAngle = (sectorAngles[i] - 90) * Math.PI / 180;
                const endAngle = (sectorAngles[(i + 1) % 8] - 90) * Math.PI / 180;
                const centerAngle = (startAngle + endAngle) / 2;

                // Color based on distance
                let color;
                if (distance < 1) {
                    color = 'rgba(255, 0, 0, 0.7)'; // Red for < 1m
                } else if (distance < 3) {
                    color = 'rgba(255, 255, 0, 0.5)'; // Yellow for < 3m
                } else {
                    color = 'rgba(0, 255, 0, 0.3)'; // Green for > 3m
                }

                // Draw sector arc
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(currentCenterX, currentCenterY, pixelDist, startAngle, endAngle);
                ctx.lineTo(currentCenterX, currentCenterY);
                ctx.fill();

                // Draw distance text
                if (distance < 25) {
                    const textX = currentCenterX + (pixelDist + 15) * Math.cos(centerAngle);
                    const textY = currentCenterY + (pixelDist + 15) * Math.sin(centerAngle);
                    ctx.fillStyle = '#00ff00';
                    ctx.font = 'bold 12px monospace';
                    ctx.fillText(`${distance.toFixed(1)}m`, textX - 15, textY + 3);
                }
            }

            // Draw center point
            ctx.fillStyle = '#00ff00';
            ctx.beginPath();
            ctx.arc(currentCenterX, currentCenterY, 3, 0, Math.PI * 2);
            ctx.fill();

            // Update proximity values panel
            const valuesHtml = sectorNames.map((name, i) => {
                const dist = distances[i] / 100;
                const className = dist < 1 ? 'danger' : dist < 3 ? 'warning' : 'safe';
                return `
                    <div class="proximity-item">
                        <div class="proximity-label">${name}</div>
                        <div class="proximity-value ${className}">${dist.toFixed(1)}m</div>
                    </div>
                `;
            }).join('');
            document.getElementById('proximity-values').innerHTML = valuesHtml;
        }

        function updateStatus(elementId, data) {
            const element = document.getElementById(elementId);
            let html = '';

            for (const [key, value] of Object.entries(data)) {
                const displayKey = key.replace(/_/g, ' ').toUpperCase();
                let displayValue = value;
                let className = 'status-value';

                // Apply color coding
                if (value === 'RUNNING' || value === 'Connected' || value === 'Good') {
                    className += ' status-ok';
                } else if (value === 'Warning' || value === 'Degraded') {
                    className += ' status-warning';
                } else if (value === 'ERROR' || value === 'Disconnected' || value === 'Failed') {
                    className += ' status-error';
                }

                html += `
                    <div class="status-label">${displayKey}:</div>
                    <div class="${className}">${displayValue}</div>
                `;
            }

            element.innerHTML = html;
        }

        let lastCropCaptureCount = 0;
        let lastImageUpdate = 0;
        
        function updateCropMonitor(cropData) {
            const statusElement = document.getElementById('crop-status');
            const imageElement = document.getElementById('crop-image');
            const currentTime = new Date().getTime();
            
            // Update image more frequently - every 3 seconds or when capture count changes
            const shouldUpdateImage = (cropData.capture_count !== lastCropCaptureCount) || 
                                    (currentTime - lastImageUpdate > 3000);
            
            if (shouldUpdateImage) {
                const timestamp = new Date().getTime();
                imageElement.src = `/api/crop/image?t=${timestamp}`;
                lastCropCaptureCount = cropData.capture_count;
                lastImageUpdate = currentTime;
            }
            
            // Update status with better status colors
            let statusClass = 'status-ok';
            if (cropData.status === 'WARNING') statusClass = 'status-warning';
            if (cropData.status === 'STOPPED' || cropData.status === 'ERROR') statusClass = 'status-error';
            
            let statusHtml = `
                <div>Status: <span class="${statusClass}">${cropData.status}</span></div>
                <div>Captures: ${cropData.capture_count}</div>
                <div>Last: ${cropData.last_capture}</div>
                <div>Size: ${Math.round(cropData.image_size / 1024)}KB</div>
                <div>Age: ${cropData.image_age || 0}s</div>
                <div>Refresh: Every 5s</div>
                <div>Updated: ${new Date().toLocaleTimeString()}</div>
            `;
            statusElement.innerHTML = statusHtml;
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/telemetry');
                const data = await response.json();

                // Update radar
                drawRadar(data.proximity);

                // Update status panels
                updateStatus('system-status', data.system_status);
                updateStatus('sensor-health', data.sensor_health);
                updateStatus('statistics', data.statistics);
                
                // Update crop monitor
                if (data.crop_monitor) {
                    updateCropMonitor(data.crop_monitor);
                }

                // Update timestamp
                document.getElementById('timestamp').textContent =
                    new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }

        // Initial draw
        drawRadar([2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]);

        // Update every 1 second for faster crop image refresh
        setInterval(updateDashboard, 1000);
        
        // Force rover vision image update every 5 seconds
        setInterval(function() {
            const imageElement = document.getElementById('crop-image');
            if (imageElement) {
                const timestamp = new Date().getTime();
                imageElement.src = `/api/crop/image?t=${timestamp}`;
                console.log('Rover vision image refreshed at', new Date().toLocaleTimeString());
            }
        }, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/telemetry')
def get_telemetry():
    """Return current telemetry data as JSON"""
    return jsonify(telemetry_data)

@app.route('/api/proximity/<int:sector>/<int:distance>')
def update_proximity(sector, distance):
    """Update proximity data for a specific sector"""
    if 0 <= sector < 8:
        telemetry_data['proximity'][sector] = distance
        telemetry_data['statistics']['last_update'] = datetime.now().strftime('%H:%M:%S')
    return jsonify({'status': 'ok'})

@app.route('/api/crop/image')
def get_crop_image():
    """Serve the latest crop monitor image"""
    from flask import send_file, Response
    import os
    import io
    from PIL import Image, ImageDraw, ImageFont
    
    image_path = "/tmp/crop_latest.jpg"
    if os.path.exists(image_path):
        # Add cache-busting headers to prevent browser caching
        response = send_file(image_path, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        # Create a placeholder image
        try:
            # Create a 640x480 placeholder image
            img = Image.new('RGB', (640, 480), color='black')
            draw = ImageDraw.Draw(img)
            
            # Add text
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
            
            text = "ROVER VISION\nNo Image Available"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (640 - text_width) // 2
            y = (480 - text_height) // 2
            
            draw.text((x, y), text, fill='green', font=font)
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            
            return Response(img_byte_arr.getvalue(), mimetype='image/jpeg')
        except:
            return "No crop image available", 404

@app.route('/api/crop/status')
def get_crop_status():
    """Get crop monitor status"""
    import os
    import json
    import time
    
    status_file = "/tmp/crop_monitor_v8.json"
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                data = json.load(f)
                # Add file modification time
                data['status_file_age'] = time.time() - os.path.getmtime(status_file)
                return jsonify(data)
        except Exception as e:
            return jsonify({'error': f'Failed to read status file: {e}'})
    
    # Check if latest image exists
    latest_image_exists = os.path.exists('/tmp/crop_latest.jpg')
    latest_image_size = os.path.getsize('/tmp/crop_latest.jpg') if latest_image_exists else 0
    latest_image_age = time.time() - os.path.getmtime('/tmp/crop_latest.jpg') if latest_image_exists else 0
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'capture_count': 0,
        'image_path': '/tmp/crop_latest.jpg',
        'image_size': latest_image_size,
        'latest_image_exists': latest_image_exists,
        'latest_image_age_seconds': latest_image_age,
        'status': 'crop_monitor_not_running'
    })

def read_telemetry_file():
    """Read telemetry from shared file (if proximity bridge writes to file)"""
    while True:
        # FIX BUG #14: Better error handling for file read failures
        try:
            with open('/tmp/proximity_v8.json', 'r') as f:
                data = json.load(f)
                telemetry_data['proximity'] = data.get('sectors_cm', [2500] * 8)
                telemetry_data['statistics']['messages_sent'] = data.get('messages_sent', 0)
                telemetry_data['statistics']['last_update'] = datetime.now().strftime('%H:%M:%S')
                
                # Update system status based on data availability
                telemetry_data['system_status'] = {
                    'proximity_bridge': 'RUNNING' if data.get('sectors_cm') else 'STOPPED',
                    'data_relay': 'RUNNING',  # Assume running if dashboard is up
                    'crop_monitor': 'RUNNING'  # Assume running if dashboard is up
                }
                
                # Calculate success rates for sensors
                lidar_attempts = data.get('lidar_attempts', 0)
                lidar_success = data.get('lidar_success', 0)
                if lidar_attempts > 0:
                    telemetry_data['statistics']['rplidar_success_rate'] = int((lidar_success / lidar_attempts) * 100)
                else:
                    telemetry_data['statistics']['rplidar_success_rate'] = 0
                
                # Update sensor health based on error counts
                lidar_errors = data.get('lidar_errors', 0)
                telemetry_data['sensor_health'] = {
                    'rplidar': 'Good' if lidar_errors == 0 else 'Warning' if lidar_errors < 5 else 'Error',
                    'realsense': 'Connected' if data.get('realsense_cm') else 'Disconnected',
                    'pixhawk': 'Connected'  # Assume connected if messages are being sent
                }
                
                # Update additional statistics
                if 'timestamp' in data:
                    age = time.time() - data['timestamp']
                    telemetry_data['statistics']['uptime'] = int(age)
                
                # Update crop monitor status
                try:
                    crop_status_file = "/tmp/crop_monitor_v8.json"
                    crop_image_file = "/tmp/crop_latest.jpg"
                    
                    if os.path.exists(crop_status_file):
                        with open(crop_status_file, 'r') as f:
                            crop_data = json.load(f)
                            # Check if image file exists and is recent
                            image_exists = os.path.exists(crop_image_file)
                            image_age = 0
                            if image_exists:
                                image_age = time.time() - os.path.getmtime(crop_image_file)
                            
                            # Determine status based on data freshness
                            if image_age < 10:  # Image is less than 10 seconds old
                                status = 'RUNNING'
                            elif image_age < 60:  # Image is less than 1 minute old
                                status = 'WARNING'
                            else:
                                status = 'STOPPED'
                                
                            telemetry_data['crop_monitor'] = {
                                'status': status,
                                'capture_count': crop_data.get('capture_count', 0),
                                'last_capture': crop_data.get('timestamp', 'Unknown'),
                                'image_size': crop_data.get('image_size', 0),
                                'image_age': int(image_age)
                            }
                    else:
                        telemetry_data['crop_monitor'] = {
                            'status': 'STOPPED',
                            'capture_count': 0,
                            'last_capture': 'Never',
                            'image_size': 0,
                            'image_age': 999
                        }
                except Exception as e:
                    telemetry_data['crop_monitor'] = {
                        'status': 'ERROR',
                        'capture_count': 0,
                        'last_capture': f'Error: {str(e)[:20]}',
                        'image_size': 0,
                        'image_age': 999
                    }
                    
        except FileNotFoundError:
            # File doesn't exist yet - expected on startup
            telemetry_data['system_status'] = {
                'proximity_bridge': 'STOPPED',
                'data_relay': 'Unknown',
                'crop_monitor': 'Unknown'
            }
            telemetry_data['sensor_health'] = {
                'rplidar': 'Unknown',
                'realsense': 'Unknown',
                'pixhawk': 'Unknown'
            }
        except PermissionError as e:
            print(f"[ERROR] Permission denied reading telemetry file: {e}")
        except json.JSONDecodeError as e:
            print(f"[WARNING] Invalid JSON in telemetry file: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error reading telemetry: {e}")

        time.sleep(0.5)

def simulate_data():
    """Simulate telemetry data for testing"""
    import random
    while True:
        # Simulate proximity data
        for i in range(8):
            if random.random() < 0.3:  # 30% chance of obstacle
                telemetry_data['proximity'][i] = random.randint(50, 500)
            else:
                telemetry_data['proximity'][i] = 2500

        # Update statistics
        telemetry_data['statistics']['uptime'] += 1
        telemetry_data['statistics']['messages_sent'] += random.randint(5, 15)
        telemetry_data['statistics']['last_update'] = datetime.now().strftime('%H:%M:%S')
        telemetry_data['statistics']['rplidar_success_rate'] = random.randint(94, 98)
        telemetry_data['statistics']['realsense_fps'] = random.randint(28, 30)

        # Update status
        telemetry_data['system_status'] = {
            'proximity_bridge': 'RUNNING',
            'data_relay': 'RUNNING',
            'crop_monitor': 'RUNNING' if random.random() > 0.1 else 'STOPPED'
        }

        telemetry_data['sensor_health'] = {
            'rplidar': 'Good' if random.random() > 0.05 else 'Warning',
            'realsense': 'Connected',
            'pixhawk': 'Connected'
        }

        time.sleep(0.5)

if __name__ == '__main__':
    import sys

    # Start background thread for data updates
    if '--simulate' in sys.argv:
        print("Starting in simulation mode...")
        data_thread = threading.Thread(target=simulate_data, daemon=True)
    else:
        print("Starting in production mode...")
        print("Reading telemetry from /tmp/proximity_v8.json")
        data_thread = threading.Thread(target=read_telemetry_file, daemon=True)

    data_thread.start()

    # Start Flask server
    print("\n" + "="*50)
    print("PROJECT ASTRA NZ - TELEMETRY DASHBOARD V8")
    print("="*50)
    print(f"Dashboard (Local): http://0.0.0.0:8081")
    print(f"Dashboard (Network): http://172.25.11.86:8081")
    print(f"API Endpoint: http://0.0.0.0:8081/api/telemetry")
    print("="*50 + "\n")

    app.run(host='0.0.0.0', port=8081, debug=False)
