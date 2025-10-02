#!/usr/bin/env python3
"""
Project Astra NZ - Dashboard Receiver V4
Receives data from rover and forwards to dashboard
Runs on Windows EC2 instance
"""

from flask import Flask, request, jsonify, render_template_string
import json
import base64
import os
from datetime import datetime
import threading
import queue

app = Flask(__name__)

# Configuration
LISTEN_PORT = 8081
DASHBOARD_URL = "http://localhost:8080"
IMAGE_DIR = "C:\\MissionControlServer\\images"
DATA_DIR = "C:\\MissionControlServer\\data"

# Ensure directories exist
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Global storage
latest_telemetry = {}
command_queue = []
image_history = []

# HTML template for status page
STATUS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Astra NZ Receiver Status</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f0f0f0; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #2c3e50; }
        .status { padding: 10px; margin: 10px 0; background: #ecf0f1; border-radius: 5px; }
        .telemetry { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .section { background: #f8f9fa; padding: 15px; border-radius: 8px; }
        .image-section { text-align: center; }
        img { max-width: 100%; height: auto; border-radius: 8px; margin: 10px 0; }
        button { padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #2980b9; }
        .timestamp { color: #7f8c8d; font-size: 12px; }
    </style>
    <script>
        function requestImage() {
            fetch('/request_image', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    setTimeout(() => location.reload(), 5000);
                });
        }
        
        setInterval(() => location.reload(), 10000);  // Auto refresh every 10s
    </script>
</head>
<body>
    <div class="container">
        <h1>🚜 Project Astra NZ - Dashboard Receiver</h1>
        
        <div class="status">
            <strong>Status:</strong> {{ status }}<br>
            <strong>Last Update:</strong> {{ last_update }}<br>
            <strong>Images Today:</strong> {{ image_count }}
        </div>
        
        <div class="telemetry">
            <div class="section">
                <h3>📍 GPS Status</h3>
                <p>Latitude: {{ telemetry.gps.lat|round(6) }}</p>
                <p>Longitude: {{ telemetry.gps.lon|round(6) }}</p>
                <p>Altitude: {{ telemetry.gps.alt|round(2) }}m</p>
                <p>Fix Type: {{ telemetry.gps.fix }}</p>
            </div>
            
            <div class="section">
                <h3>🔋 Battery</h3>
                <p>Voltage: {{ telemetry.battery.voltage|round(2) }}V</p>
                <p>Current: {{ telemetry.battery.current|round(2) }}A</p>
                <p>Remaining: {{ telemetry.battery.remaining }}%</p>
            </div>
        </div>
        
        <div class="section">
            <h3>🧭 Proximity (Sectors)</h3>
            {% if telemetry.proximity and telemetry.proximity.sectors_cm %}
                <p>Min Distance: {{ telemetry.proximity.min_cm }} cm</p>
                <p>Forward (0,1,7): {{ telemetry.proximity.sectors_cm[0] }}, {{ telemetry.proximity.sectors_cm[1] }}, {{ telemetry.proximity.sectors_cm[7] }}</p>
                <p>All: {{ telemetry.proximity.sectors_cm }}</p>
            {% else %}
                <p>No proximity data yet</p>
            {% endif %}
        </div>
        
        <div class="image-section">
            <h3>📸 Crop Monitoring</h3>
            {% if latest_image %}
                <img src="/image/latest" alt="Latest crop image">
                <p class="timestamp">Captured: {{ latest_image_time }}</p>
            {% else %}
                <p>No images received yet</p>
            {% endif %}
            <br>
            <button onclick="requestImage()">📸 Request New Image</button>
            <p style="color: #7f8c8d; font-size: 12px;">Requests remaining today: {{ requests_remaining }}/5</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def status_page():
    """Display receiver status"""
    return render_template_string(STATUS_PAGE,
        status="Connected" if latest_telemetry else "Waiting for data",
        last_update=latest_telemetry.get('timestamp', 'Never'),
        image_count=len(image_history),
        telemetry=latest_telemetry if latest_telemetry else {
            'gps': {'lat': 0, 'lon': 0, 'alt': 0, 'fix': 0},
            'battery': {'voltage': 0, 'current': 0, 'remaining': 0}
        },
        latest_image=len(image_history) > 0,
        latest_image_time=image_history[-1]['timestamp'] if image_history else None,
        requests_remaining=5 - len([c for c in command_queue if c['timestamp'].date() == datetime.now().date()])
    )

@app.route('/telemetry', methods=['POST'])
def receive_telemetry():
    """Receive telemetry data from rover"""
    global latest_telemetry
    
    try:
        data = request.json
        latest_telemetry = data
        
        # Save telemetry to file
        filename = os.path.join(DATA_DIR, f"telemetry_{datetime.now().strftime('%Y%m%d')}.json")
        with open(filename, 'a') as f:
            f.write(json.dumps(data) + '\n')
            
        # Forward to main dashboard
        # In production, implement proper forwarding to localhost:8080
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/image', methods=['POST'])
def receive_image():
    """Receive image from rover"""
    global image_history
    
    try:
        data = request.json
        
        # Decode image
        image_data = base64.b64decode(data['image'])
        
        # Save image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"crop_{data['type']}_{timestamp}.jpg"
        filepath = os.path.join(IMAGE_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
            
        # Update history
        image_history.append({
            'filename': filename,
            'timestamp': datetime.now(),
            'type': data['type'],
            'telemetry': data.get('telemetry', {})
        })
        
        # Keep only last 100 images in memory
        if len(image_history) > 100:
            image_history = image_history[-100:]
            
        print(f"✓ Image received: {filename} ({data['type']})")
        
        # Forward to main dashboard
        # In production, implement proper forwarding
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f"✗ Image receive error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/image/latest')
def get_latest_image():
    """Serve the latest image"""
    if image_history:
        latest = image_history[-1]
        filepath = os.path.join(IMAGE_DIR, latest['filename'])
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return f.read(), 200, {'Content-Type': 'image/jpeg'}
    return "No image", 404

@app.route('/commands', methods=['GET'])
def get_commands():
    """Return pending commands for rover"""
    global command_queue
    
    # Get commands and clear queue
    commands = command_queue.copy()
    command_queue = []
    
    return jsonify(commands), 200

@app.route('/request_image', methods=['POST'])
def request_image():
    """Add image capture command to queue"""
    global command_queue
    
    # Check rate limit (5 per day)
    today_requests = [c for c in command_queue 
                     if c['timestamp'].date() == datetime.now().date()]
    
    if len(today_requests) >= 5:
        return jsonify({'message': 'Daily limit reached (5 requests)'}), 429
        
    command_queue.append({
        'type': 'capture_image',
        'timestamp': datetime.now()
    })
    
    return jsonify({'message': 'Image capture requested'}), 200

def cleanup_old_files():
    """Clean up files older than 30 days"""
    import glob
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=30)
    
    # Clean old images
    for filepath in glob.glob(os.path.join(IMAGE_DIR, "*.jpg")):
        if os.path.getctime(filepath) < cutoff.timestamp():
            os.remove(filepath)
            print(f"Cleaned old image: {os.path.basename(filepath)}")
            
def forward_to_dashboard(data_type, data):
    """Forward data to main dashboard on :8080"""
    # In production, implement proper HTTP forwarding
    # to your existing dashboard at localhost:8080
    pass

def main():
    """Main execution"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - Dashboard Receiver V4")
    print("=" * 60)
    print(f"Listening on port {LISTEN_PORT}")
    print(f"Image directory: {IMAGE_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print("=" * 60)
    print("\nEndpoints:")
    print(f"  • Status page: http://localhost:{LISTEN_PORT}/")
    print(f"  • Telemetry: POST to /telemetry")
    print(f"  • Images: POST to /image")
    print(f"  • Commands: GET from /commands")
    print("=" * 60)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=lambda: cleanup_old_files())
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=LISTEN_PORT, debug=False)

if __name__ == "__main__":
    main()