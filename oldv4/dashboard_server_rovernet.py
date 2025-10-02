#!/usr/bin/env python3
"""
Project Astra NZ - Rovernet Dashboard Server
Configured for rovernet network (4753CF475F287023)
Windows UGV-Server IP: 172.25.77.186
"""

import json
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

class SystemStatus(BaseModel):
    rplidar: Dict
    realsense: Dict  
    pixhawk: Dict
    dashboard: Dict

class RoverDataPacket(BaseModel):
    timestamp: float
    rover_id: str
    system_status: SystemStatus
    lidar_data: List[Dict]
    camera_data: Optional[Dict]
    telemetry_data: List[Dict]

class DashboardServer:
    def __init__(self):
        self.app = FastAPI(title="Project Astra NZ Rovernet Dashboard", version="1.0")
        
        # Data storage
        self.rover_data_buffer = deque(maxlen=1000)
        self.current_rover_status = {}
        self.connected_websockets = set()
        
        # Statistics
        self.stats = {
            'packets_received': 0,
            'last_packet_time': 0,
            'uptime_start': time.time(),
            'rovers_connected': set()
        }
        
        self.setup_routes()
        
    def setup_routes(self):
        """Setup all API routes and WebSocket endpoints"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            return self.get_dashboard_html()
        
        @self.app.post("/api/rover_data")
        async def receive_rover_data(data: RoverDataPacket):
            """Receive data from rover relay system"""
            try:
                # Update statistics
                self.stats['packets_received'] += 1
                self.stats['last_packet_time'] = time.time()
                self.stats['rovers_connected'].add(data.rover_id)
                
                # Store data
                data_dict = data.dict()
                data_dict['server_timestamp'] = time.time()
                self.rover_data_buffer.append(data_dict)
                
                # Update current status
                self.current_rover_status[data.rover_id] = data_dict
                
                # Broadcast to WebSocket clients
                await self.broadcast_to_websockets(data_dict)
                
                print(f"Received data from {data.rover_id} - "
                      f"LiDAR: {len(data.lidar_data)} scans, "
                      f"Camera: {'✓' if data.camera_data else '✗'}, "
                      f"Telemetry: {len(data.telemetry_data)} msgs")
                
                return {"status": "success", "timestamp": time.time()}
                
            except Exception as e:
                print(f"Error processing rover data: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/status")
        async def get_server_status():
            """Get dashboard server status"""
            uptime = time.time() - self.stats['uptime_start']
            
            return {
                'server_status': 'running',
                'uptime_seconds': round(uptime, 1),
                'packets_received': self.stats['packets_received'],
                'rovers_connected': list(self.stats['rovers_connected']),
                'websocket_clients': len(self.connected_websockets),
                'last_data_age': round(time.time() - self.stats['last_packet_time'], 1) if self.stats['last_packet_time'] > 0 else None,
                'buffer_size': len(self.rover_data_buffer),
                'network': 'rovernet (4753CF475F287023)',
                'server_ip': '172.25.77.186'
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.connected_websockets.add(websocket)
            print("WebSocket client connected")
            
            try:
                # Send current status on connection
                if self.current_rover_status:
                    await websocket.send_json({
                        'type': 'initial_data',
                        'data': self.current_rover_status
                    })
                
                # Keep connection alive
                while True:
                    await websocket.receive_text()
                    
            except WebSocketDisconnect:
                print("WebSocket client disconnected")
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                self.connected_websockets.discard(websocket)

    async def broadcast_to_websockets(self, data: Dict):
        """Broadcast data to all connected WebSocket clients"""
        if not self.connected_websockets:
            return
            
        message = {
            'type': 'rover_update',
            'data': data
        }
        
        websockets_to_remove = []
        
        for websocket in self.connected_websockets.copy():
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"Failed to send WebSocket message: {e}")
                websockets_to_remove.append(websocket)
        
        for websocket in websockets_to_remove:
            self.connected_websockets.discard(websocket)

    def get_dashboard_html(self) -> str:
        """Generate dashboard HTML page"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Astra NZ - Rovernet Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        body { 
            font-family: 'Arial', sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: #1a1a1a; 
            color: #ffffff;
        }
        .header {
            background: linear-gradient(135deg, #2c5530, #4a7c59);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .network-info {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #4a7c59;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .status-card {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #4a7c59;
        }
        .status-card h3 {
            margin: 0 0 15px 0;
            color: #4a7c59;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-ok { background-color: #4ade80; }
        .status-warning { background-color: #fbbf24; }
        .status-error { background-color: #ef4444; }
        
        .sensor-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .lidar-display {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .camera-display {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .camera-image {
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            border: 2px solid #4a7c59;
        }
        #lidarCanvas {
            background: #1a1a1a;
            border-radius: 5px;
            border: 2px solid #4a7c59;
        }
        .telemetry-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .telemetry-item {
            background: #3a3a3a;
            padding: 15px;
            border-radius: 8px;
        }
        .telemetry-label {
            font-size: 0.9em;
            color: #aaa;
            margin-bottom: 5px;
        }
        .telemetry-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #4a7c59;
        }
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 5px;
            font-weight: bold;
        }
        .connected { background: #4ade80; color: #000; }
        .disconnected { background: #ef4444; color: #fff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚜 Project Astra NZ - Rovernet Dashboard</h1>
        <p>Real-time agricultural rover monitoring system</p>
    </div>

    <div class="network-info">
        <h3>🌐 Network Configuration</h3>
        <p><strong>Network:</strong> rovernet (4753CF475F287023)</p>
        <p><strong>Server IP:</strong> 172.25.77.186:8080</p>
        <p><strong>Status:</strong> <span id="serverStatus">Starting...</span></p>
    </div>

    <div id="connectionStatus" class="connection-status disconnected">Connecting...</div>

    <div class="status-grid">
        <div class="status-card">
            <h3>System Status</h3>
            <div id="systemStatus">
                <p><span id="rplidarStatus" class="status-indicator status-error"></span>RPLidar S3: <span id="rplidarText">Disconnected</span></p>
                <p><span id="realsenseStatus" class="status-indicator status-error"></span>RealSense D435i: <span id="realsenseText">Disconnected</span></p>
                <p><span id="pixhawkStatus" class="status-indicator status-error"></span>Pixhawk 6C: <span id="pixhawkText">Disconnected</span></p>
            </div>
        </div>
        
        <div class="status-card">
            <h3>Data Statistics</h3>
            <div id="dataStats">
                <p>Packets Received: <span id="packetsReceived">0</span></p>
                <p>Last Update: <span id="lastUpdate">Never</span></p>
                <p>Update Rate: <span id="updateRate">0.0 Hz</span></p>
                <p>Connected Rovers: <span id="connectedRovers">0</span></p>
            </div>
        </div>
    </div>

    <div class="sensor-data">
        <div class="lidar-display">
            <h3>LiDAR S3 - 360° Scan</h3>
            <canvas id="lidarCanvas" width="400" height="400"></canvas>
            <p>Range: 0.2m to 25m | Update: <span id="lidarUpdate">Never</span></p>
        </div>
        
        <div class="camera-display">
            <h3>RealSense D435i Camera</h3>
            <img id="cameraImage" class="camera-image" src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjI0MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMmEyYTJhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZpbGw9IiNhYWEiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIwLjNlbSI+Tm8gQ2FtZXJhIERhdGE8L3RleHQ+PC9zdmc+" alt="Camera feed">
            <div id="obstacleInfo">
                <p>Forward Distance: <span id="forwardDistance">--</span>m</p>
                <p>Obstacle Alert: <span id="obstacleAlert">No</span></p>
            </div>
        </div>
    </div>

    <div class="status-card">
        <h3>Telemetry Data</h3>
        <div class="telemetry-grid" id="telemetryGrid">
            <div class="telemetry-item">
                <div class="telemetry-label">Latitude</div>
                <div class="telemetry-value">--°</div>
            </div>
            <div class="telemetry-item">
                <div class="telemetry-label">Longitude</div>
                <div class="telemetry-value">--°</div>
            </div>
            <div class="telemetry-item">
                <div class="telemetry-label">Ground Speed</div>
                <div class="telemetry-value">-- m/s</div>
            </div>
            <div class="telemetry-item">
                <div class="telemetry-label">Heading</div>
                <div class="telemetry-value">--°</div>
            </div>
        </div>
    </div>

    <script>
        class DashboardApp {
            constructor() {
                this.ws = null;
                this.connectWebSocket();
                this.lastUpdateTime = 0;
                this.updateRateBuffer = [];
                this.setupLidarCanvas();
                this.updateServerStatus();
            }

            connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                
                try {
                    this.ws = new WebSocket(wsUrl);
                    
                    this.ws.onopen = () => {
                        console.log('WebSocket connected to rovernet dashboard');
                        this.updateConnectionStatus(true);
                        this.ws.send(JSON.stringify({type: 'ping'}));
                    };
                    
                    this.ws.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        this.handleWebSocketMessage(message);
                    };
                    
                    this.ws.onclose = () => {
                        console.log('WebSocket disconnected');
                        this.updateConnectionStatus(false);
                        setTimeout(() => this.connectWebSocket(), 3000);
                    };
                    
                } catch (error) {
                    console.error('WebSocket connection error:', error);
                    this.updateConnectionStatus(false);
                    setTimeout(() => this.connectWebSocket(), 5000);
                }
            }

            handleWebSocketMessage(message) {
                if (message.type === 'rover_update') {
                    this.updateDashboard(message.data);
                } else if (message.type === 'initial_data') {
                    Object.values(message.data).forEach(roverData => {
                        this.updateDashboard(roverData);
                    });
                }
            }

            updateConnectionStatus(connected) {
                const status = document.getElementById('connectionStatus');
                if (connected) {
                    status.textContent = 'Connected to Rovernet';
                    status.className = 'connection-status connected';
                } else {
                    status.textContent = 'Disconnected';
                    status.className = 'connection-status disconnected';
                }
            }

            updateDashboard(data) {
                this.updateSystemStatus(data.system_status);
                this.updateDataStats(data);
                if (data.lidar_data && data.lidar_data.length > 0) {
                    this.updateLidarDisplay(data.lidar_data[data.lidar_data.length - 1]);
                }
                if (data.camera_data) {
                    this.updateCameraDisplay(data.camera_data);
                }
                if (data.telemetry_data && data.telemetry_data.length > 0) {
                    this.updateTelemetry(data.telemetry_data);
                }
            }

            updateSystemStatus(status) {
                if (!status) return;
                
                const sensors = ['rplidar', 'realsense', 'pixhawk'];
                
                sensors.forEach(sensor => {
                    const indicator = document.getElementById(`${sensor}Status`);
                    const text = document.getElementById(`${sensor}Text`);
                    
                    if (status[sensor] && status[sensor].connected) {
                        indicator.className = 'status-indicator status-ok';
                        const age = (Date.now() / 1000) - status[sensor].last_update;
                        text.textContent = `Connected (${Math.round(age)}s ago)`;
                    } else {
                        indicator.className = 'status-indicator status-error';
                        text.textContent = 'Disconnected';
                    }
                });
            }

            updateDataStats(data) {
                const now = Date.now() / 1000;
                const age = now - data.timestamp;
                document.getElementById('lastUpdate').textContent = `${Math.round(age)}s ago`;
                
                // Calculate update rate
                if (this.lastUpdateTime > 0) {
                    const timeDiff = now - this.lastUpdateTime;
                    if (timeDiff > 0) {
                        const rate = 1.0 / timeDiff;
                        this.updateRateBuffer.push(rate);
                        if (this.updateRateBuffer.length > 10) {
                            this.updateRateBuffer.shift();
                        }
                        const avgRate = this.updateRateBuffer.reduce((a, b) => a + b, 0) / this.updateRateBuffer.length;
                        document.getElementById('updateRate').textContent = `${avgRate.toFixed(1)} Hz`;
                    }
                }
                this.lastUpdateTime = now;
            }

            setupLidarCanvas() {
                this.lidarCanvas = document.getElementById('lidarCanvas');
                this.lidarCtx = this.lidarCanvas.getContext('2d');
            }

            updateLidarDisplay(lidarData) {
                if (!lidarData || !lidarData.data) return;
                
                const ctx = this.lidarCtx;
                const canvas = this.lidarCanvas;
                const centerX = canvas.width / 2;
                const centerY = canvas.height / 2;
                const maxRadius = Math.min(centerX, centerY) - 20;
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw range circles
                ctx.strokeStyle = '#444';
                ctx.lineWidth = 1;
                for (let r = maxRadius / 4; r <= maxRadius; r += maxRadius / 4) {
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, r, 0, 2 * Math.PI);
                    ctx.stroke();
                }
                
                // Draw cross hairs
                ctx.beginPath();
                ctx.moveTo(centerX, centerY - maxRadius);
                ctx.lineTo(centerX, centerY + maxRadius);
                ctx.moveTo(centerX - maxRadius, centerY);
                ctx.lineTo(centerX + maxRadius, centerY);
                ctx.stroke();
                
                // Draw LiDAR points
                ctx.fillStyle = '#4a7c59';
                lidarData.data.forEach(point => {
                    const angle = (point.angle - 90) * Math.PI / 180;
                    const distance = Math.min(point.distance, 2500);
                    const radius = (distance / 2500) * maxRadius;
                    
                    const x = centerX + radius * Math.cos(angle);
                    const y = centerY + radius * Math.sin(angle);
                    
                    ctx.beginPath();
                    ctx.arc(x, y, 2, 0, 2 * Math.PI);
                    ctx.fill();
                });
                
                // Draw rover position
                ctx.fillStyle = '#ef4444';
                ctx.beginPath();
                ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI);
                ctx.fill();
                
                document.getElementById('lidarUpdate').textContent = 'Live';
            }

            updateCameraDisplay(cameraData) {
                if (cameraData.image) {
                    const img = document.getElementById('cameraImage');
                    img.src = `data:image/jpeg;base64,${cameraData.image}`;
                }
                
                if (cameraData.obstacles) {
                    document.getElementById('forwardDistance').textContent = 
                        cameraData.obstacles.forward_min || '--';
                    document.getElementById('obstacleAlert').textContent = 
                        cameraData.obstacles.obstacle_detected ? 'YES' : 'No';
                }
            }

            updateTelemetry(telemetryData) {
                const latest = telemetryData[telemetryData.length - 1];
                if (!latest) return;
                
                const grid = document.getElementById('telemetryGrid');
                let items = [];
                
                if (latest.type === 'position') {
                    items = [
                        {label: 'Latitude', value: latest.lat?.toFixed(7) || '--', unit: '°'},
                        {label: 'Longitude', value: latest.lon?.toFixed(7) || '--', unit: '°'},
                        {label: 'Ground Speed', value: latest.vx?.toFixed(1) || '--', unit: 'm/s'},
                        {label: 'Heading', value: latest.hdg?.toFixed(1) || '--', unit: '°'}
                    ];
                } else if (latest.type === 'hud') {
                    items = [
                        {label: 'Ground Speed', value: latest.groundspeed?.toFixed(1) || '--', unit: 'm/s'},
                        {label: 'Heading', value: latest.heading?.toFixed(1) || '--', unit: '°'},
                        {label: 'Throttle', value: latest.throttle || '--', unit: '%'},
                        {label: 'Altitude', value: latest.alt?.toFixed(1) || '--', unit: 'm'}
                    ];
                }
                
                if (items.length > 0) {
                    grid.innerHTML = items.map(item => `
                        <div class="telemetry-item">
                            <div class="telemetry-label">${item.label}</div>
                            <div class="telemetry-value">${item.value} ${item.unit}</div>
                        </div>
                    `).join('');
                }
            }

            async updateServerStatus() {
                try {
                    const response = await fetch('/api/status');
                    const status = await response.json();
                    
                    document.getElementById('serverStatus').textContent = 
                        `${status.server_status} (${status.uptime_seconds}s)`;
                    document.getElementById('packetsReceived').textContent = status.packets_received;
                    document.getElementById('connectedRovers').textContent = status.rovers_connected.length;
                    
                } catch (error) {
                    console.error('Failed to fetch server status:', error);
                }
                
                setTimeout(() => this.updateServerStatus(), 5000);
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            new DashboardApp();
        });
    </script>
</body>
</html>"""

def main():
    """Start the dashboard server"""
    print("Project Astra NZ Rovernet Dashboard Server")
    print("==========================================")
    print("Network: rovernet (4753CF475F287023)")
    print("Server IP: 172.25.77.186:8080")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Waiting for rover data from Project Astra...")
    
    dashboard = DashboardServer()
    
    uvicorn.run(
        dashboard.app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )

if __name__ == "__main__":
    main()
