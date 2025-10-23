#!/usr/bin/env python3
"""
Project Astra NZ - Web Telemetry Dashboard V9
Modern, compact rover telemetry dashboard with no-scroll design
Real-time monitoring interface for proximity sensors, GPS, and system status

FUNCTIONALITY:
- Displays real-time rover telemetry data in a compact, single-screen layout
- Shows proximity radar, GPS coordinates, power status, and system health
- Provides live rover vision feed with space-optimized image handling
- Updates data every second with smooth animations and color-coded status
- Serves as the main monitoring interface for rover operations

COMPONENTS:
- Flask web server for HTTP interface
- Real-time data updates via JavaScript polling
- Proximity radar visualization with obstacle detection
- GPS and power monitoring with MAVLink integration
- System resource monitoring (CPU, memory, disk usage)
- Crop monitor integration with image streaming

USAGE:
- Run: python3 telemetry_dashboard_v9.py
- Access: http://0.0.0.0:8081 (local) or http://172.25.77.186:8081 (network)
- No command line arguments required
- Automatically reads telemetry data from /tmp/proximity_v8.json and /tmp/crop_monitor_v9.json
"""

import json
import time
import threading
import os
from datetime import datetime
from flask import Flask, render_template_string, jsonify, send_file, Response
import numpy as np
import io
from PIL import Image, ImageDraw, ImageFont

# ============================================================================
# DEPENDENCY IMPORTS AND CONFIGURATION
# ============================================================================

# Try to import optional dependencies with graceful fallback
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("[WARNING] flask-cors not installed - CORS disabled")

# Import sensor libraries (optional for dashboard operation)
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

# Initialize Flask application with CORS support
app = Flask(__name__)
if CORS_AVAILABLE:
    CORS(app)

# ============================================================================
# GLOBAL TELEMETRY DATA STRUCTURE
# ============================================================================
# This dictionary stores all telemetry data that gets displayed on the dashboard
# Updated in real-time by reading from shared files written by other components
telemetry_data = {
    # Proximity sensor data - 8 sectors around rover (in centimeters)
    # Each sector represents distance to nearest obstacle in that direction
    'proximity': [2500] * 8,  # Default: 25m (2500cm) - no obstacles detected
    
    # System component status - tracks if each component is running
    'system_status': {
        'proximity_bridge': 'Unknown',  # Main sensor fusion component
        'data_relay': 'Unknown',       # Data transmission component
        'crop_monitor': 'Unknown',     # Image capture component
        'rover_manager': 'Unknown'      # System management component
    },
    
    # Sensor hardware health - tracks individual sensor status
    'sensor_health': {
        'rplidar': 'Unknown',      # 360-degree LiDAR sensor
        'realsense': 'Unknown',    # Depth and color camera
        'pixhawk': 'Unknown'       # Flight controller/autopilot
    },
    
    # GPS and navigation data from Pixhawk via MAVLink
    'gps_data': {
        'latitude': 0.0,           # GPS latitude coordinate
        'longitude': 0.0,          # GPS longitude coordinate
        'altitude': 0.0,            # GPS altitude (meters)
        'heading': 0.0,             # Compass heading (degrees)
        'speed': 0.0,               # Ground speed (m/s)
        'satellites': 0,            # Number of GPS satellites
        'fix_quality': 'No Fix'     # GPS fix quality (No Fix, 2D, 3D, DGPS, RTK)
    },
    
    # Power system data from Pixhawk
    'power_data': {
        'battery_voltage': 0.0,     # Battery voltage (volts)
        'battery_current': 0.0,     # Battery current (amps)
        'battery_percentage': 0,    # Battery charge percentage
        'power_consumption': 0.0,   # Total power consumption (watts)
        'charging_status': 'Unknown' # Charging status
    },
    
    # Navigation and flight control data
    'navigation': {
        'flight_mode': 'Unknown',   # Pixhawk flight mode (MANUAL, AUTO, etc.)
        'armed_status': 'Unknown',  # Whether rover is armed for operation
        'gps_accuracy': 0.0,        # GPS position accuracy (meters)
        'home_distance': 0.0        # Distance to home position (meters)
    },
    
    # System statistics and performance metrics
    'statistics': {
        'uptime': 0,                    # System uptime (seconds)
        'messages_sent': 0,             # MAVLink messages sent
        'last_update': '',               # Timestamp of last data update
        'rplidar_success_rate': 0,      # LiDAR scan success rate (%)
        'realsense_fps': 0              # RealSense camera frame rate
    }
}

# ============================================================================
# HTML DASHBOARD TEMPLATE
# ============================================================================
# This is the complete HTML/CSS/JavaScript for the dashboard interface
# Features:
# - Modern dark theme with neon accents
# - Compact single-screen layout (no scrolling)
# - Real-time data updates via JavaScript
# - Responsive design for different screen sizes
# - Color-coded status indicators
# - Interactive proximity radar visualization
# - Live rover vision feed with image streaming
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Project Astra NZ - Rover Telemetry Dashboard V9</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg-primary: #0a0a0a;
            --bg-secondary: #1a1a1a;
            --bg-card: #2d2d2d;
            --accent-green: #00ff88;
            --accent-yellow: #ffaa00;
            --accent-red: #ff4444;
            --accent-blue: #0088ff;
            --text-primary: #ffffff;
            --text-secondary: #888888;
            --border-color: #333333;
        }
        
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            overflow: hidden;
        }
        
        .dashboard {
            height: 100vh;
            display: grid;
            grid-template-rows: auto 1fr auto;
            grid-template-columns: 1fr;
            gap: 8px;
            padding: 8px;
        }
        
        .header {
            text-align: center;
            padding: 12px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        
        .header h1 {
            font-size: 20px;
            color: var(--accent-green);
            text-shadow: 0 0 10px var(--accent-green);
            margin-bottom: 4px;
        }
        
        .header .status {
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .status-row {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: var(--accent-green);
            box-shadow: 0 4px 8px rgba(0,255,136,0.1);
        }
        
        .card-header {
            font-size: 12px;
            font-weight: bold;
            color: var(--accent-green);
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .card-content {
            font-size: 11px;
            line-height: 1.3;
        }
        
        .status-ok { color: var(--accent-green); }
        .status-warning { color: var(--accent-yellow); }
        .status-error { color: var(--accent-red); }
        .status-info { color: var(--accent-blue); }
        
        .radar-section {
            height: 250px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .radar-container {
            position: relative;
            width: 200px;
            height: 200px;
        }
        
        .radar {
            width: 100%;
            height: 100%;
        }
        
        .bottom-row {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
        }
        
        .vision-card {
            grid-column: 1;
        }
        
        .vision-image {
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-radius: 4px;
            border: 1px solid var(--border-color);
        }
        
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            font-size: 10px;
        }
        
        .data-item {
            display: flex;
            justify-content: space-between;
            padding: 2px 0;
        }
        
        .data-label {
            color: var(--text-secondary);
        }
        
        .data-value {
            font-weight: bold;
        }
        
        .proximity-values {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 4px;
            margin-top: 6px;
        }
        
        .proximity-item {
            text-align: center;
            padding: 2px;
            background: var(--bg-primary);
            border-radius: 3px;
            font-size: 9px;
        }
        
        .proximity-label {
            color: var(--text-secondary);
        }
        
        .proximity-value {
            font-weight: bold;
            font-size: 10px;
        }
        
        .safe { color: var(--accent-green); }
        .warning { color: var(--accent-yellow); }
        .danger { color: var(--accent-red); }
        
        .icon {
            font-size: 14px;
        }
        
        @media (max-width: 1200px) {
            .status-row, .bottom-row {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        
        @media (max-width: 800px) {
            .status-row, .bottom-row {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🚀 ROVER TELEMETRY DASHBOARD V9</h1>
            <div class="status">Last Update: <span id="timestamp">--:--:--</span></div>
        </div>
        
        <div class="status-row">
            <div class="card">
                <div class="card-header">
                    <span class="icon">🖥️</span> SYSTEM
                </div>
                <div class="card-content" id="system-status">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🔍</span> SENSORS
                </div>
                <div class="card-content" id="sensor-health">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🛰️</span> GPS
                </div>
                <div class="card-content" id="gps-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🔋</span> POWER
                </div>
                <div class="card-content" id="power-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🧭</span> NAV
                </div>
                <div class="card-content" id="navigation">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
        </div>
        
        <div class="radar-section">
            <div class="radar-container">
                <canvas id="radar" class="radar"></canvas>
            </div>
        </div>
        
        <div class="bottom-row">
            <div class="card vision-card">
                <div class="card-header">
                    <span class="icon">📹</span> VISION
                </div>
                <div class="card-content">
                    <img id="vision-image" class="vision-image" src="/api/crop/image" alt="Rover Vision">
                    <div class="data-grid" id="vision-status">
                        <!-- Populated by JavaScript -->
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🎯</span> MISSION
                </div>
                <div class="card-content" id="mission-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">📊</span> TELEMETRY
                </div>
                <div class="card-content" id="telemetry-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">📝</span> LOGS
                </div>
                <div class="card-content" id="logs-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="icon">🔧</span> DEBUG
                </div>
                <div class="card-content" id="debug-data">
                    <!-- Populated by JavaScript -->
                </div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('radar');
        const ctx = canvas.getContext('2d');
        
        function resizeRadar() {
            const container = canvas.parentElement;
            const size = Math.min(container.clientWidth - 20, container.clientHeight - 20);
            canvas.width = size;
            canvas.height = size;
        }
        
        resizeRadar();
        window.addEventListener('resize', resizeRadar);
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const maxRadius = Math.min(canvas.width, canvas.height) / 2 - 10;

        const sectorAngles = [-22.5, 22.5, 67.5, 112.5, 157.5, -157.5, -112.5, -67.5];
        const sectorNames = ['F', 'FR', 'R', 'BR', 'B', 'BL', 'L', 'FL'];

        function drawRadar(distances) {
            const currentCenterX = canvas.width / 2;
            const currentCenterY = canvas.height / 2;
            const currentMaxRadius = Math.min(canvas.width, canvas.height) / 2 - 10;
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Draw grid circles
            ctx.strokeStyle = '#003300';
            ctx.lineWidth = 1;
            for (let r = 0.25; r <= 1; r += 0.25) {
                ctx.beginPath();
                ctx.arc(currentCenterX, currentCenterY, currentMaxRadius * r, 0, Math.PI * 2);
                ctx.stroke();

                ctx.fillStyle = '#004400';
                ctx.font = '8px monospace';
                ctx.fillText(`${Math.round(r * 25)}m`, currentCenterX + 5, currentCenterY - currentMaxRadius * r + 8);
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
                const distance = distances[i] / 100;
                const normalizedDist = Math.min(distance / 25, 1);
                const pixelDist = normalizedDist * currentMaxRadius;

                const startAngle = (sectorAngles[i] - 90) * Math.PI / 180;
                const endAngle = (sectorAngles[(i + 1) % 8] - 90) * Math.PI / 180;
                const centerAngle = (startAngle + endAngle) / 2;

                let color;
                if (distance < 1) {
                    color = 'rgba(255, 68, 68, 0.7)';
                } else if (distance < 3) {
                    color = 'rgba(255, 170, 0, 0.5)';
                } else {
                    color = 'rgba(0, 255, 136, 0.3)';
                }

                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(currentCenterX, currentCenterY, pixelDist, startAngle, endAngle);
                ctx.lineTo(currentCenterX, currentCenterY);
                ctx.fill();

                if (distance < 25) {
                    const textX = currentCenterX + (pixelDist + 10) * Math.cos(centerAngle);
                    const textY = currentCenterY + (pixelDist + 10) * Math.sin(centerAngle);
                    ctx.fillStyle = '#00ff88';
                    ctx.font = 'bold 8px monospace';
                    ctx.fillText(`${distance.toFixed(1)}m`, textX - 10, textY + 3);
                }
            }

            ctx.fillStyle = '#00ff88';
            ctx.beginPath();
            ctx.arc(currentCenterX, currentCenterY, 2, 0, Math.PI * 2);
            ctx.fill();
        }

        function updateCard(elementId, data, formatFunction = null) {
            const element = document.getElementById(elementId);
            let html = '';

            for (const [key, value] of Object.entries(data)) {
                const displayKey = key.replace(/_/g, ' ').toUpperCase();
                let displayValue = value;
                let className = 'data-value';

                if (value === 'RUNNING' || value === 'Connected' || value === 'Good' || value === 'OK') {
                    className += ' status-ok';
                } else if (value === 'Warning' || value === 'Degraded' || value === 'WARNING') {
                    className += ' status-warning';
                } else if (value === 'ERROR' || value === 'Disconnected' || value === 'Failed' || value === 'STOPPED') {
                    className += ' status-error';
                } else if (typeof value === 'number' && value > 0) {
                    className += ' status-info';
                }

                if (formatFunction) {
                    displayValue = formatFunction(key, value);
                }

                html += `
                    <div class="data-item">
                        <span class="data-label">${displayKey}:</span>
                        <span class="${className}">${displayValue}</span>
                    </div>
                `;
            }

            element.innerHTML = html;
        }

        function formatGPS(key, value) {
            if (key === 'latitude' || key === 'longitude') {
                return value.toFixed(6);
            } else if (key === 'altitude') {
                return `${value.toFixed(1)}m`;
            } else if (key === 'speed') {
                return `${value.toFixed(1)}m/s`;
            } else if (key === 'heading') {
                return `${value.toFixed(0)}°`;
            }
            return value;
        }

        function formatPower(key, value) {
            if (key === 'battery_voltage') {
                return `${value.toFixed(1)}V`;
            } else if (key === 'battery_current') {
                return `${value.toFixed(1)}A`;
            } else if (key === 'battery_percentage') {
                return `${value}%`;
            } else if (key === 'power_consumption') {
                return `${value.toFixed(1)}W`;
            }
            return value;
        }

        let lastVisionUpdate = 0;
        
        function updateVision(visionData) {
            const imageElement = document.getElementById('vision-image');
            const statusElement = document.getElementById('vision-status');
            const currentTime = new Date().getTime();
            
            if (currentTime - lastVisionUpdate > 3000) {
                const timestamp = new Date().getTime();
                imageElement.src = `/api/crop/image?t=${timestamp}`;
                lastVisionUpdate = currentTime;
            }
            
            let statusHtml = `
                <div class="data-item">
                    <span class="data-label">Status:</span>
                    <span class="data-value status-ok">${visionData.status}</span>
                </div>
                <div class="data-item">
                    <span class="data-label">FPS:</span>
                    <span class="data-value status-info">${visionData.fps || 30}</span>
                </div>
                <div class="data-item">
                    <span class="data-label">Quality:</span>
                    <span class="data-value status-info">${visionData.quality || 95}%</span>
                </div>
                <div class="data-item">
                    <span class="data-label">Size:</span>
                    <span class="data-value status-info">${Math.round(visionData.image_size / 1024)}KB</span>
                </div>
            `;
            statusElement.innerHTML = statusHtml;
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/telemetry');
                const data = await response.json();

                drawRadar(data.proximity);
                updateCard('system-status', data.system_status);
                updateCard('sensor-health', data.sensor_health);
                updateCard('gps-data', data.gps_data, formatGPS);
                updateCard('power-data', data.power_data, formatPower);
                updateCard('navigation', data.navigation);
                
                if (data.vision) {
                    updateVision(data.vision);
                }

                document.getElementById('timestamp').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }

        drawRadar([2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]);
        setInterval(updateDashboard, 1000);
        
        setInterval(function() {
            const imageElement = document.getElementById('vision-image');
            if (imageElement) {
                const timestamp = new Date().getTime();
                imageElement.src = `/api/crop/image?t=${timestamp}`;
            }
        }, 5000);
    </script>
</body>
</html>
'''

# ============================================================================
# FLASK ROUTES - WEB INTERFACE ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """
    Main dashboard page route
    Returns the complete HTML dashboard interface
    """
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/telemetry')
def get_telemetry():
    """
    API endpoint for real-time telemetry data
    Returns current telemetry data as JSON for JavaScript updates
    Called every second by the dashboard JavaScript
    """
    return jsonify(telemetry_data)

@app.route('/api/crop/image')
def get_crop_image():
    """
    Serve the latest rover vision image
    Returns the most recent image captured by the crop monitor
    If no image is available, creates a placeholder image
    """
    image_path = "/tmp/crop_latest.jpg"
    
    # Check if latest image exists
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/jpeg')
    else:
        # Create placeholder image when no rover vision is available
        try:
            # Create a black 320x240 image
            img = Image.new('RGB', (320, 240), color='black')
            draw = ImageDraw.Draw(img)
            
            # Try to load a nice font, fallback to default if not available
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Add "No Image Available" text
            text = "ROVER VISION\nNo Image Available"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Center the text
            x = (320 - text_width) // 2
            y = (240 - text_height) // 2
            
            draw.text((x, y), text, fill='green', font=font)
            
            # Convert to JPEG bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            
            return Response(img_byte_arr.getvalue(), mimetype='image/jpeg')
        except:
            return "No crop image available", 404

# ============================================================================
# TELEMETRY DATA READING FUNCTIONS
# ============================================================================

def read_telemetry_file():
    """
    Background thread function that continuously reads telemetry data
    from shared files written by other rover components
    
    This function runs in a separate thread and updates the global
    telemetry_data dictionary with real-time information from:
    - /tmp/proximity_v8.json (proximity bridge data)
    - /tmp/crop_monitor_v9.json (crop monitor data)
    
    Updates include:
    - Proximity sensor data (8 sectors)
    - System component status
    - Sensor health information
    - GPS and navigation data
    - Power system data
    - Statistics and performance metrics
    """
    while True:
        try:
            # Read proximity data from proximity bridge component
            with open('/tmp/proximity_v8.json', 'r') as f:
                data = json.load(f)
                
                # Update proximity sensor data (8 sectors in centimeters)
                telemetry_data['proximity'] = data.get('sectors_cm', [2500] * 8)
                
                # Update statistics
                telemetry_data['statistics']['messages_sent'] = data.get('messages_sent', 0)
                telemetry_data['statistics']['last_update'] = datetime.now().strftime('%H:%M:%S')
                
                # Update system component status based on data availability
                telemetry_data['system_status'] = {
                    'proximity_bridge': 'RUNNING' if data.get('sectors_cm') else 'STOPPED',
                    'data_relay': 'RUNNING',
                    'crop_monitor': 'RUNNING',
                    'rover_manager': 'RUNNING'
                }
                
                # Update sensor health
                lidar_errors = data.get('lidar_errors', 0)
                telemetry_data['sensor_health'] = {
                    'rplidar': 'Good' if lidar_errors == 0 else 'Warning' if lidar_errors < 5 else 'Error',
                    'realsense': 'Connected' if data.get('realsense_cm') else 'Disconnected',
                    'pixhawk': 'Connected'
                }
                
                # Update GPS data from MAVLink
                if 'gps_data' in data:
                    gps = data['gps_data']
                    telemetry_data['gps_data'] = {
                        'latitude': gps.get('latitude', 0.0),
                        'longitude': gps.get('longitude', 0.0),
                        'altitude': gps.get('altitude', 0.0),
                        'heading': gps.get('heading', 0.0),
                        'speed': gps.get('speed', 0.0),
                        'satellites': gps.get('satellites', 0),
                        'fix_quality': gps.get('fix_quality', 'No Fix')
                    }
                
                # Update power data
                if 'power_data' in data:
                    power = data['power_data']
                    telemetry_data['power_data'] = {
                        'battery_voltage': power.get('voltage', 0.0),
                        'battery_current': power.get('current', 0.0),
                        'battery_percentage': power.get('percentage', 0),
                        'power_consumption': power.get('consumption', 0.0),
                        'charging_status': power.get('charging', 'Unknown')
                    }
                
                # Update navigation data
                if 'navigation' in data:
                    nav = data['navigation']
                    telemetry_data['navigation'] = {
                        'flight_mode': nav.get('mode', 'Unknown'),
                        'armed_status': nav.get('armed', 'Unknown'),
                        'gps_accuracy': nav.get('accuracy', 0.0),
                        'home_distance': nav.get('home_distance', 0.0)
                    }
                
                # Update statistics
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
                            image_exists = os.path.exists(crop_image_file)
                            image_age = 0
                            if image_exists:
                                image_age = time.time() - os.path.getmtime(crop_image_file)
                            
                            if image_age < 10:
                                status = 'RUNNING'
                            elif image_age < 60:
                                status = 'WARNING'
                            else:
                                status = 'STOPPED'
                                
                            telemetry_data['vision'] = {
                                'status': status,
                                'fps': crop_data.get('fps', 30),
                                'quality': crop_data.get('quality', 95),
                                'image_size': crop_data.get('image_size', 0),
                                'capture_count': crop_data.get('capture_count', 0)
                            }
                    else:
                        telemetry_data['vision'] = {
                            'status': 'STOPPED',
                            'fps': 0,
                            'quality': 0,
                            'image_size': 0,
                            'capture_count': 0
                        }
                except Exception as e:
                    telemetry_data['vision'] = {
                        'status': 'ERROR',
                        'fps': 0,
                        'quality': 0,
                        'image_size': 0,
                        'capture_count': 0
                    }
                    
        except FileNotFoundError:
            telemetry_data['system_status'] = {
                'proximity_bridge': 'STOPPED',
                'data_relay': 'Unknown',
                'crop_monitor': 'Unknown',
                'rover_manager': 'Unknown'
            }
        except Exception as e:
            print(f"[ERROR] Unexpected error reading telemetry: {e}")

        time.sleep(0.5)

def simulate_data():
    """Simulate telemetry data for testing"""
    import random
    while True:
        # Simulate proximity data
        for i in range(8):
            if random.random() < 0.3:
                telemetry_data['proximity'][i] = random.randint(50, 500)
            else:
                telemetry_data['proximity'][i] = 2500

        # Update statistics
        telemetry_data['statistics']['uptime'] += 1
        telemetry_data['statistics']['messages_sent'] += random.randint(5, 15)
        telemetry_data['statistics']['last_update'] = datetime.now().strftime('%H:%M:%S')
        telemetry_data['statistics']['rplidar_success_rate'] = random.randint(94, 98)
        telemetry_data['statistics']['realsense_fps'] = random.randint(28, 30)

        # Update system status
        telemetry_data['system_status'] = {
            'proximity_bridge': 'RUNNING',
            'data_relay': 'RUNNING',
            'crop_monitor': 'RUNNING',
            'rover_manager': 'RUNNING'
        }

        telemetry_data['sensor_health'] = {
            'rplidar': 'Good' if random.random() > 0.05 else 'Warning',
            'realsense': 'Connected',
            'pixhawk': 'Connected'
        }

        # Simulate GPS data
        telemetry_data['gps_data'] = {
            'latitude': -41.2924 + random.uniform(-0.001, 0.001),
            'longitude': 174.7787 + random.uniform(-0.001, 0.001),
            'altitude': 10.0 + random.uniform(-2, 2),
            'heading': random.uniform(0, 360),
            'speed': random.uniform(0, 5),
            'satellites': random.randint(8, 15),
            'fix_quality': '3D Fix'
        }

        # Simulate power data
        telemetry_data['power_data'] = {
            'battery_voltage': 12.6 + random.uniform(-0.5, 0.5),
            'battery_current': 2.3 + random.uniform(-0.5, 0.5),
            'battery_percentage': random.randint(80, 95),
            'power_consumption': 28.5 + random.uniform(-5, 5),
            'charging_status': 'Not Charging'
        }

        # Simulate navigation data
        telemetry_data['navigation'] = {
            'flight_mode': 'AUTO',
            'armed_status': 'Armed',
            'gps_accuracy': random.uniform(1.0, 3.0),
            'home_distance': random.uniform(0, 100)
        }

        # Simulate vision data
        telemetry_data['vision'] = {
            'status': 'RUNNING',
            'fps': random.randint(28, 30),
            'quality': random.randint(90, 98),
            'image_size': random.randint(50, 200) * 1024,
            'capture_count': random.randint(100, 1000)
        }

        time.sleep(0.5)

# ============================================================================
# MAIN EXECUTION - DASHBOARD STARTUP
# ============================================================================

if __name__ == '__main__':
    import sys

    # Check for simulation mode (for testing without hardware)
    if '--simulate' in sys.argv:
        print("Starting in simulation mode...")
        print("  - Using simulated telemetry data")
        print("  - No hardware dependencies required")
        data_thread = threading.Thread(target=simulate_data, daemon=True)
    else:
        print("Starting in production mode...")
        print("  - Reading telemetry from /tmp/proximity_v8.json")
        print("  - Reading crop monitor data from /tmp/crop_monitor_v9.json")
        data_thread = threading.Thread(target=read_telemetry_file, daemon=True)

    # Start background thread for telemetry data updates
    data_thread.start()

    # Display startup information
    print("\n" + "="*50)
    print("PROJECT ASTRA NZ - TELEMETRY DASHBOARD V9")
    print("="*50)
    print(f"Dashboard (Local): http://0.0.0.0:8081")
    print(f"Dashboard (Network): http://172.25.77.186:8081")
    print(f"API Endpoint: http://0.0.0.0:8081/api/telemetry")
    print("="*50 + "\n")

    # Start Flask web server
    # host='0.0.0.0' allows access from network
    # port=8081 is the standard rover dashboard port
    # debug=False for production use
    app.run(host='0.0.0.0', port=8081, debug=False)
