#!/usr/bin/env python3
"""
Project Astra NZ - Web Telemetry Dashboard V9
Real-time monitoring interface for proximity sensors and system status - Bug Fixes from V7
"""

import json
import time
import threading
import os
import socket
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for
# Make numpy optional; dashboard should not crash if it's missing
try:
    import numpy as np
except Exception:
    np = None

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
app.secret_key = os.environ.get('ASTRA_DASHBOARD_SECRET', 'astra-dashboard-secret')
SIGNUP_SECRET = os.environ.get('ASTRA_SIGNUP_CODE', 'LETMEIN')
USERS_FILE = '/tmp/astra_dashboard_users.json'

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[AUTH] Failed to load users: {e}")
    # Default built-in admin
    return {"admin": "admin"}

def save_users(users: dict) -> None:
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
    except Exception as e:
        print(f"[AUTH] Failed to save users: {e}")

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
    <title>Project Astra NZ - Telemetry Dashboard V9</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg: #0F2845;
            --bg-elev: #1A3A5A;
            --card: #1E3A5F;
            --card-border: rgba(0, 255, 255, 0.35);
            --text: #FFFFFF;
            --muted: rgba(255, 255, 255, 0.75);
            --accent: #00FFFF; /* cyan */
            --accent-strong: #00CCCC;
            --cyan: #00FFFF;
            --cyan-glow: rgba(0, 255, 255, 0.6);
            --cyan-light: rgba(0, 255, 255, 0.15);
            --ok: #22C55E;
            --warn: #F59E0B;
            --error: #EF4444;
            --green: #22C55E;
            --orange: #F59E0B;
            --red: #EF4444;
            --chip: rgba(0, 255, 255, 0.12);
            --chip-border: rgba(0, 255, 255, 0.25);
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            --radius: 14px;
            --radius-sm: 10px;
        }
        /* Sport variant (inspired by red cluster rings) */
        html[data-theme="sport"] {
            --accent: #fb7185; /* rose */
            --accent-strong: #f43f5e;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #0F2845 0%, #1A3A5A 100%);
            color: var(--text);
            padding: 16px;
            min-height: 100vh;
            overflow-x: hidden;
        }
        .header {
            width: 100%;
            margin: 0 0 6px 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 16px;
            background: linear-gradient(135deg, var(--card) 0%, rgba(30, 58, 95, 0.9) 100%);
            border: 2px solid rgba(0, 255, 255, 0.35);
            border-radius: var(--radius);
            box-shadow: 0 0 30px rgba(0, 255, 255, 0.25);
            flex-shrink: 0;
        }
        .header h1 {
            font-size: 20px;
            letter-spacing: 0.15em;
            font-weight: 700;
            margin: 0;
            color: var(--cyan);
            text-shadow: 0 0 20px var(--cyan-glow);
        }
        #timestamp {
            background: rgba(0, 255, 255, 0.12);
            color: var(--text);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 13px;
            border: 1px solid var(--cyan);
            font-weight: 700;
        }
        .actions {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .btn {
            padding: 4px 8px;
            border-radius: 8px;
            border: 1px solid var(--card-border);
            background: var(--chip);
            color: var(--text);
            font-size: 11px;
            cursor: pointer;
        }
        .btn:hover { filter: brightness(1.1); }
        .container {
            width: 100%;
            margin: 0 0 6px 0;
            display: flex;
            gap: 8px;
            overflow: hidden;
            flex-shrink: 0;
        }
        .container.status-row {
            margin: 0 0 6px 0;
        }
        .container.status-row .panel {
            flex: 1;
            min-width: 0;
        }
        /* Indicator ribbon */
        .ribbon {
            width: 100%;
            margin: 0 0 6px 0;
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 6px;
            flex-shrink: 0;
        }
        .light {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: var(--radius-sm);
            box-shadow: var(--shadow);
            font-size: 11px;
            color: var(--muted);
        }
        .dot {
            width: 10px; height: 10px; border-radius: 50%;
            box-shadow: 0 0 0 2px rgba(255,255,255,0.06) inset, 0 0 12px rgba(0,0,0,0.3);
            background: rgba(255,255,255,0.08);
        }
        .on-ok { background: #22c55e; box-shadow: 0 0 12px rgba(34,197,94,0.8); animation: breathe 2.6s ease-in-out infinite; }
        .on-warn { background: #f59e0b; box-shadow: 0 0 12px rgba(245,158,11,0.8); animation: pulse 1.4s ease-in-out infinite; }
        .on-err { background: #ef4444; box-shadow: 0 0 12px rgba(239,68,68,0.8); animation: pulse 0.9s ease-in-out infinite; }
        @keyframes pulse { 0%,100% { transform: scale(0.95); } 50% { transform: scale(1.15); } }
        @keyframes breathe { 0%,100% { filter: saturate(0.9); } 50% { filter: saturate(1.2); } }
        .rover-vision-container {
            grid-column: 1 / -1;
            margin-top: 0;
        }
        .vision-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 0;
            align-items: start;
            width: 100%;
            flex: 1;
            min-height: 0;
            overflow: hidden;
        }
        .proximity-panel {
            grid-column: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .rover-vision-panel {
            grid-column: 2;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .proximity-panel .panel,
        .rover-vision-panel .panel {
            width: 100%;
            height: 100%;
            margin: 0;
            align-items: center;
        }
        .proximity-panel .radar-container {
            width: 100%;
            max-width: 320px;
            aspect-ratio: 1 / 1;
            margin: 0 auto;
            flex-shrink: 0;
        }
        .proximity-panel .radar {
            width: 100%;
            height: 100%;
        }
        .panel {
            background: linear-gradient(135deg, var(--card) 0%, rgba(30, 58, 95, 0.9) 100%);
            border: 1px solid rgba(0, 255, 255, 0.35);
            border-radius: var(--radius);
            padding: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), 0 0 20px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            transition: all 0.3s ease;
        }
        .panel:hover {
            border-color: var(--cyan);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4), 0 0 30px rgba(0, 255, 255, 0.35);
            transform: translateY(-2px);
        }
        .panel:before {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.05), transparent);
            animation: shine 4s infinite;
            pointer-events: none;
        }
        @keyframes shine {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        .panel h2 {
            font-size: 14px;
            margin-bottom: 12px;
            color: var(--cyan);
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--cyan-glow);
        }
        .radar-container {
            position: relative;
            width: 280px;
            height: 280px;
            min-height: 280px;
            margin: 0 auto;
            border-radius: 50%;
            border: 1px solid rgba(0, 255, 255, 0.35);
            background: radial-gradient(circle, rgba(0, 255, 255, 0.12) 0%, transparent 70%);
            box-shadow: inset 0 0 40px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .radar-container:after {
            content: "";
            position: absolute;
            inset: -6px;
            border-radius: 50%;
            background: conic-gradient(from 0deg, transparent 0deg, rgba(255,255,255,0.0) 260deg, var(--cyan) 300deg, transparent 360deg);
            animation: spin 6s linear infinite;
            filter: blur(1px);
            opacity: 0.35;
            pointer-events: none;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .radar {
            width: 100%;
            height: 100%;
        }
        .gallery-grid { 
            display: none; 
            margin-top: 8px;
            overflow-x: auto;
            overflow-y: hidden;
        }
        .gallery-grid.active { 
            display: flex;
            flex-direction: row;
            gap: 8px;
            padding-bottom: 4px;
        }
        .gallery-grid::-webkit-scrollbar {
            height: 6px;
        }
        .gallery-grid::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.05);
            border-radius: 3px;
        }
        .gallery-grid::-webkit-scrollbar-thumb {
            background: var(--accent);
            border-radius: 3px;
        }
        .thumb {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 6px;
            text-align: center;
            min-width: 120px;
            flex-shrink: 0;
            cursor: pointer;
        }
        .thumb img { width: 100%; height: 80px; object-fit: cover; border-radius: 6px; }
        .thumb .cap { color: var(--muted); font-size: 10px; margin-top: 4px; white-space: nowrap; }
        .status-grid {
            display: flex;
            flex-direction: column;
            gap: 4px;
            font-size: 11px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }
        .status-label {
            color: var(--muted);
            font-size: 10px;
            white-space: nowrap;
        }
        .status-value {
            text-align: right;
            padding: 2px 6px;
            border-radius: 999px;
            border: 1px solid var(--card-border);
            background: var(--chip);
            font-size: 11px;
            white-space: nowrap;
        }
        .status-ok { color: var(--green); background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.18); }
        .status-warning { color: var(--orange); background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.18); }
        .status-error { color: var(--red); background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.18); }
        .status-value { background: rgba(0, 255, 255, 0.15); border: 1px solid var(--cyan); }
        .proximity-values {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 4px;
            margin-top: 8px;
            width: 100%;
            max-width: 480px;
        }
        .proximity-item {
            text-align: center;
            padding: 5px 3px;
            background: var(--chip);
            border: 1px solid var(--chip-border);
            border-radius: var(--radius-sm);
        }
        .proximity-label {
            font-size: 9px;
            color: var(--muted);
            letter-spacing: 0.06em;
        }
        .proximity-value {
            font-size: 12px;
            font-weight: 700;
        }
        .safe { color: var(--ok); }
        .warning { color: var(--warn); }
        .danger { color: var(--error); }
        .crop-image-container {
            text-align: center;
            margin-top: 0;
            width: 100%;
            max-width: 320px;
            aspect-ratio: 1 / 1;
            margin-left: auto;
            margin-right: auto;
            display: grid;
            place-items: center;
            flex-shrink: 0;
        }
        .crop-image-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
            border: 1px solid var(--card-border);
            box-shadow: var(--shadow);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }
        .crop-image-container img:hover {
            box-shadow: 0 12px 28px rgba(0,0,0,0.45);
            transform: scale(1.015);
        }
        .rover-vision-container .panel {
            padding: 10px;
        }
        .rover-vision-container h2 {
            font-size: 12px;
            text-align: center;
            margin-bottom: 8px;
        }
        .vision-toolbar {
            display: flex;
            gap: 6px;
            justify-content: center;
            margin-bottom: 6px;
            flex-shrink: 0;
        }
        .btn.small { 
            padding: 4px 8px; 
            font-size: 11px;
            transition: all 0.2s ease;
        }
        .alert-offline {
            display: none;
            padding: 14px 16px;
            margin-top: 8px;
            text-align: center;
            color: #f59e0b;
            background: rgba(245,158,11,0.08);
            border: 1px solid rgba(245,158,11,0.28);
            border-radius: var(--radius-sm);
        }
        @media (max-width: 980px) {
            .vision-row { 
                grid-template-columns: 1fr;
                gap: 12px;
            }
            .proximity-panel, .rover-vision-panel { grid-column: 1; }
            .header h1 { font-size: 14px; }
            .actions { flex-wrap: wrap; gap: 4px; }
        }
        @media (max-width: 640px) {
            .container { grid-template-columns: 1fr; }
            .ribbon { grid-template-columns: repeat(3, 1fr); }
            body { padding: 8px; }
        }
        /* Room boundary map */
        .room-map { width: 100%; height: 140px; margin: 4px 0 0 0; border:1px dashed var(--card-border); border-radius: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 ROVER TELEMETRY DASHBOARD</h1>
        <div class="actions">
            <span class="btn" id="metric-uptime" title="Uptime">Uptime: --</span>
            <span class="btn" id="metric-fps" title="RealSense FPS">FPS: --</span>
            <span class="btn" id="metric-msg" title="Messages Sent">Msgs: --</span>
            <button class="btn" id="theme-toggle" title="Toggle theme">Classic/Sport</button>
            <p id="timestamp">--:--:--</p>
        </div>
    </div>

    <div class="ribbon" id="status-ribbon">
        <div class="light"><span class="dot" id="light-proximity"></span> Proximity</div>
        <div class="light"><span class="dot" id="light-relay"></span> Data Relay</div>
        <div class="light"><span class="dot" id="light-crop"></span> Crop Monitor</div>
        <div class="light"><span class="dot" id="light-lidar"></span> RPLidar</div>
        <div class="light"><span class="dot" id="light-realsense"></span> RealSense</div>
        <div class="light"><span class="dot" id="light-pixhawk"></span> Pixhawk</div>
    </div>

    <div class="container status-row">
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
                <div class="vision-toolbar">
                    <button class="btn small" id="btn-live">Live</button>
                    <button class="btn small" id="btn-snap">Snapshots</button>
                    <button class="btn small" id="btn-gallery">Gallery</button>
                    <span style="flex:1"></span>
                    <button class="btn small" id="btn-color">Color</button>
                    <button class="btn small" id="btn-depth">Depth</button>
                    <button class="btn small" id="btn-ir">IR</button>
                </div>
                <div class="crop-image-container">
                    <img id="live-stream" src="/api/stream" alt="Live Stream" style="display:none"
                         onerror="this.style.display='none'; document.getElementById('vision-offline').style.display='block';"
                         onload="this.style.display='block'; document.getElementById('vision-offline').style.display='none';">
                    <div id="vision-offline" style="color: var(--muted); font-size: 12px; padding: 20px; text-align: center;">
                        Camera offline or not available
                    </div>
                </div>
                <div id="inline-gallery" class="gallery-grid">
                    <!-- Gallery items will be populated here -->
                </div>
            </div>
        </div>
    </div>

    <div class="container" style="flex-shrink: 0;">
        <div class="panel" style="width: 100%;">
            <h2>ENVIRONMENT BOUNDARY (10m)</h2>
            <canvas id="room-map" class="room-map"></canvas>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('radar');
        const ctx = canvas.getContext('2d');
        const roomMap = document.getElementById('room-map');
        const roomCtx = roomMap.getContext('2d');
        
        // Make radar fit the container size
        function resizeRadar() {
            const container = canvas.parentElement;
            const size = container.clientWidth;
            canvas.width = size;
            canvas.height = size;
        }
        function resizeRoom() {
            const w = roomMap.parentElement.clientWidth - 36;
            roomMap.width = w;
            roomMap.height = 140;
        }
        
        // Initial resize
        resizeRadar();
        resizeRoom();
        
        // Resize on window resize
        window.addEventListener('resize', () => { resizeRadar(); resizeRoom(); });
        
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
            ctx.strokeStyle = 'rgba(110, 231, 183, 0.18)';
            ctx.lineWidth = 1;
            for (let r = 0.25; r <= 1; r += 0.25) {
                ctx.beginPath();
                ctx.arc(currentCenterX, currentCenterY, currentMaxRadius * r, 0, Math.PI * 2);
                ctx.stroke();

                // Distance labels
                ctx.fillStyle = 'rgba(230, 234, 242, 0.5)';
                ctx.font = '11px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
                ctx.fillText(`${Math.round(r * 25)}m`, currentCenterX + 5, currentCenterY - currentMaxRadius * r + 10);
            }

            // Draw sector lines / ticks
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
            // Minor ticks every 15°
            ctx.strokeStyle = 'rgba(110, 231, 183, 0.12)';
            for (let a = -180; a < 180; a += 15) {
                const rad = (a - 90) * Math.PI / 180;
                const inner = currentMaxRadius - 8;
                ctx.beginPath();
                ctx.moveTo(currentCenterX + inner * Math.cos(rad), currentCenterY + inner * Math.sin(rad));
                ctx.lineTo(currentCenterX + currentMaxRadius * Math.cos(rad), currentCenterY + currentMaxRadius * Math.sin(rad));
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
                    color = 'rgba(239, 68, 68, 0.65)'; // softer red
                } else if (distance < 3) {
                    color = 'rgba(245, 158, 11, 0.50)'; // amber
                } else {
                    color = 'rgba(52, 211, 153, 0.30)'; // mint
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
                    ctx.fillStyle = 'rgba(230, 234, 242, 0.85)';
                    ctx.font = '600 12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
                    ctx.fillText(`${distance.toFixed(1)}m`, textX - 15, textY + 3);
                }
            }

            // Draw center point
            ctx.fillStyle = 'rgba(110, 231, 183, 0.9)';
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

        function drawRoomBoundary(distances) {
            const w = roomMap.width, h = roomMap.height;
            roomCtx.clearRect(0,0,w,h);
            
            // Background grid
            roomCtx.strokeStyle = 'rgba(255,255,255,0.03)';
            roomCtx.lineWidth = 1;
            for (let x=0; x<w; x+=30){ roomCtx.beginPath(); roomCtx.moveTo(x,0); roomCtx.lineTo(x,h); roomCtx.stroke(); }
            for (let y=0; y<h; y+=30){ roomCtx.beginPath(); roomCtx.moveTo(0,y); roomCtx.lineTo(w,y); roomCtx.stroke(); }
            
            // Draw room walls/boundaries from obstacle data
            const cx = w/2, cy = h/2; const maxRange = 10.0; // meters
            const points = [];
            
            // Collect all sector points to form boundaries
            for (let i=0;i<8;i++){
                const dist = Math.min(distances[i]/100, maxRange);
                const angleDeg = (sectorAngles[i] + sectorAngles[(i + 1) % 8]) / 2;
                const a = (angleDeg - 90) * Math.PI/180;
                const r = (dist / maxRange) * (Math.min(w,h)/2 - 20);
                const x = cx + r*Math.cos(a), y = cy + r*Math.sin(a);
                points.push({x, y, dist, angle: angleDeg});
            }
            
            // Draw room boundary as connected walls
            if (points.length > 0) {
                roomCtx.strokeStyle = 'rgba(110, 231, 183, 0.4)';
                roomCtx.lineWidth = 2;
                roomCtx.beginPath();
                roomCtx.moveTo(points[0].x, points[0].y);
                for (let i = 1; i < points.length; i++) {
                    roomCtx.lineTo(points[i].x, points[i].y);
                }
                roomCtx.closePath();
                roomCtx.stroke();
                
                // Fill room with subtle gradient
                roomCtx.fillStyle = 'rgba(110, 231, 183, 0.05)';
                roomCtx.fill();
            }
            
            // Draw obstacles as walls/objects
            for (let i=0;i<8;i++){
                const dist = Math.min(distances[i]/100, maxRange);
                const angleDeg = (sectorAngles[i] + sectorAngles[(i + 1) % 8]) / 2;
                const a = (angleDeg - 90) * Math.PI/180;
                const r = (dist / maxRange) * (Math.min(w,h)/2 - 20);
                const x = cx + r*Math.cos(a), y = cy + r*Math.sin(a);
                
                if (dist < maxRange - 1) { // Only draw if within range
                    const size = dist < 1 ? 8 : dist < 3 ? 6 : 4;
                    roomCtx.fillStyle = dist < 1 ? 'rgba(239, 68, 68, 0.7)' : dist < 3 ? 'rgba(245, 158, 11, 0.6)' : 'rgba(52, 211, 153, 0.5)';
                    roomCtx.beginPath(); 
                    roomCtx.arc(x,y,size,0,Math.PI*2); 
                    roomCtx.fill();
                    
                    // Add glow effect for close objects
                    if (dist < 2) {
                        roomCtx.shadowColor = dist < 1 ? '#ef4444' : '#f59e0b';
                        roomCtx.shadowBlur = 8;
                        roomCtx.fillStyle = dist < 1 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.2)';
                        roomCtx.beginPath(); 
                        roomCtx.arc(x,y,size+2,0,Math.PI*2); 
                        roomCtx.fill();
                        roomCtx.shadowBlur = 0;
                    }
                }
            }
            
            // Draw center rover with direction indicator
            roomCtx.fillStyle = '#6ee7b7';
            roomCtx.beginPath(); 
            roomCtx.arc(cx,cy,4,0,Math.PI*2); 
            roomCtx.fill();
            roomCtx.strokeStyle = '#6ee7b7';
            roomCtx.lineWidth = 2;
            roomCtx.beginPath();
            roomCtx.moveTo(cx, cy-8);
            roomCtx.lineTo(cx, cy);
            roomCtx.stroke();
            
            // Label
            roomCtx.fillStyle = 'rgba(110, 231, 183, 0.8)';
            roomCtx.font = '11px system-ui, sans-serif';
            roomCtx.fillText('±10m Environment', 12, 18);
        }

        // Indicator helpers
        function setLight(id, state) {
            const el = document.getElementById(id);
            if (!el) return;
            el.classList.remove('on-ok','on-warn','on-err');
            if (state === 'ok') el.classList.add('on-ok');
            else if (state === 'warn') el.classList.add('on-warn');
            else if (state === 'err') el.classList.add('on-err');
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
                    <div class="status-item">
                        <div class="status-label">${displayKey}:</div>
                        <div class="${className}">${displayValue}</div>
                    </div>
                `;
            }

            element.innerHTML = html;
        }

        // Fetch real data from API
        function updateDashboard() {
            fetch('/api/telemetry')
                .then(response => response.json())
                .then(data => {
                    // Update radar
                    drawRadar(data.proximity);

                    // Update status panels
                    updateStatus('system-status', data.system_status);
                    updateStatus('sensor-health', data.sensor_health);
                    updateStatus('statistics', data.statistics);
                    
                    // Update ribbon lights
                    const sys = data.system_status || {};
                    const sen = data.sensor_health || {};
                    setLight('light-proximity', sys.proximity_bridge === 'RUNNING' ? 'ok' : sys.proximity_bridge === 'STOPPED' ? 'err' : 'warn');
                    setLight('light-relay', sys.data_relay === 'RUNNING' ? 'ok' : 'warn');
                    setLight('light-crop', sys.crop_monitor === 'RUNNING' ? 'ok' : sys.crop_monitor === 'STOPPED' ? 'err' : 'warn');
                    setLight('light-lidar', sen.rplidar === 'Good' ? 'ok' : sen.rplidar === 'Warning' ? 'warn' : 'err');
                    setLight('light-realsense', sen.realsense === 'Connected' ? 'ok' : 'err');
                    setLight('light-pixhawk', sen.pixhawk === 'Connected' ? 'ok' : 'warn');

                    // Update room boundary
                    drawRoomBoundary(data.proximity);

                    // Update timestamp
                    document.getElementById('timestamp').textContent = new Date().toLocaleTimeString();
                    
                    // Update header metrics
                    const stats = data.statistics || {};
                    const uptimeSecs = stats.uptime || 0;
                    const h = Math.floor(uptimeSecs / 3600).toString().padStart(2,'0');
                    const m = Math.floor((uptimeSecs % 3600)/60).toString().padStart(2,'0');
                    const s = Math.floor(uptimeSecs % 60).toString().padStart(2,'0');
                    document.getElementById('metric-uptime').textContent = `Uptime: ${h}:${m}:${s}`;
                    document.getElementById('metric-fps').textContent = `FPS: ${stats.realsense_fps || 0}`;
                    document.getElementById('metric-msg').textContent = `Msgs: ${stats.messages_sent || 0}`;
                })
                .catch(error => {
                    console.error('Error fetching telemetry:', error);
                });
        }

        // Initial draw
        drawRadar([2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]);

        // Update every 1 second
        setInterval(updateDashboard, 1000);

        // Footer credit (matching standalone design)
        (function(){
            const footer = document.createElement('div');
            footer.style.position='fixed'; 
            footer.style.bottom='12px'; 
            footer.style.right='12px'; 
            footer.style.padding='6px 12px';
            footer.style.background='rgba(0, 0, 0, 0.6)';
            footer.style.border='1px solid rgba(0, 255, 255, 0.2)';
            footer.style.borderRadius='6px';
            footer.style.fontSize='11px';
            footer.style.color='rgba(255, 255, 255, 0.7)';
            footer.style.fontWeight='500';
            footer.style.letterSpacing='0.05em';
            footer.style.zIndex='1000';
            footer.style.backdropFilter='blur(4px)';
            footer.textContent = 'Developed by Harinder Singh';
            footer.addEventListener('mouseenter', () => {
                footer.style.background='rgba(0, 0, 0, 0.8)';
                footer.style.borderColor='rgba(0, 255, 255, 0.4)';
                footer.style.color='rgba(255, 255, 255, 0.9)';
            });
            footer.addEventListener('mouseleave', () => {
                footer.style.background='rgba(0, 0, 0, 0.6)';
                footer.style.borderColor='rgba(0, 255, 255, 0.2)';
                footer.style.color='rgba(255, 255, 255, 0.7)';
            });
            document.body.appendChild(footer);
        })();

        // Vision toolbar buttons
        const btnLive = document.getElementById('btn-live');
        const btnSnap = document.getElementById('btn-snap');
        const btnGallery = document.getElementById('btn-gallery');
        const cropContainer = document.querySelector('.crop-image-container');
        const inlineGallery = document.getElementById('inline-gallery');
        const liveStream = document.getElementById('live-stream');
        const btnColor = document.getElementById('btn-color');
        const btnDepth = document.getElementById('btn-depth');
        const btnIr = document.getElementById('btn-ir');

        let currentView = 'live';
        let currentStream = 'color'; // color | depth | ir

        function applyStreamButtons() {
            // Reset
            btnColor.style.background = '';
            btnDepth.style.background = '';
            btnIr.style.background = '';
            if (currentStream === 'color') btnColor.style.background = 'var(--accent)';
            else if (currentStream === 'depth') btnDepth.style.background = 'var(--accent)';
            else if (currentStream === 'ir') btnIr.style.background = 'var(--accent)';
        }

        function updateLiveStreamSrc() {
            let url = '/api/stream';
            if (currentStream === 'depth') url = '/api/stream/depth';
            else if (currentStream === 'ir') url = '/api/stream/ir';
            liveStream.src = url + '?' + new Date().getTime();
            applyStreamButtons();
        }

        function showLiveView() {
            currentView = 'live';
            cropContainer.style.display = 'grid';
            inlineGallery.classList.remove('active');
            updateLiveStreamSrc();
            btnLive.style.background = 'var(--accent)';
            btnSnap.style.background = '';
            btnGallery.style.background = '';
        }

        function showSnapshots() {
            currentView = 'snap';
            cropContainer.style.display = 'grid';
            inlineGallery.classList.remove('active');
            liveStream.src = '/api/crop/latest?' + new Date().getTime();
            btnLive.style.background = '';
            btnSnap.style.background = 'var(--accent)';
            btnGallery.style.background = '';
        }

        function showGallery() {
            currentView = 'gallery';
            cropContainer.style.display = 'none';
            inlineGallery.classList.add('active');
            loadGallery();
            btnLive.style.background = '';
            btnSnap.style.background = '';
            btnGallery.style.background = 'var(--accent)';
        }

        function loadGallery() {
            fetch('/api/crop/list')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    if (data.images && data.images.length > 0) {
                        data.images.forEach(img => {
                            html += `
                                <div class="thumb" onclick="window.open('/api/crop/archive/${img.filename}', '_blank')">
                                    <img src="/api/crop/archive/${img.filename}" alt="${img.filename}">
                                    <div class="cap">${img.time}</div>
                                </div>
                            `;
                        });
                    } else {
                        html = '<div style="color: var(--muted); padding: 20px;">No images available</div>';
                    }
                    inlineGallery.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error loading gallery:', error);
                    inlineGallery.innerHTML = '<div style="color: var(--error); padding: 20px;">Error loading gallery</div>';
                });
        }

        btnLive.addEventListener('click', showLiveView);
        btnSnap.addEventListener('click', showSnapshots);
        btnGallery.addEventListener('click', showGallery);

        // Stream mode buttons
        btnColor.addEventListener('click', () => { currentStream = 'color'; if (currentView==='live') updateLiveStreamSrc(); });
        btnDepth.addEventListener('click', () => { currentStream = 'depth'; if (currentView==='live') updateLiveStreamSrc(); });
        btnIr.addEventListener('click', () => { currentStream = 'ir'; if (currentView==='live') updateLiveStreamSrc(); });

        // Initialize with live view
        showLiveView();

        // Theme toggle
        const themeBtn = document.getElementById('theme-toggle');
        function toggleTheme(){
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'sport' ? '' : 'sport';
            if (next) document.documentElement.setAttribute('data-theme', next);
            else document.documentElement.removeAttribute('data-theme');
        }
        themeBtn.addEventListener('click', toggleTheme);
        // Keyboard shortcut: press "t" to toggle theme
        window.addEventListener('keydown', (e) => { if ((e.key||'').toLowerCase() === 't') toggleTheme(); });
    </script>
</body>
</html>


'''

@app.route('/')
def index():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_HTML)

LOGIN_HTML = '''
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login - Astra Dashboard</title>
<style>
:root {
    --bg: #0F2845;
    --card: #1E3A5F;
    --text: #FFFFFF;
    --cyan: #00FFFF;
    --cyan-glow: rgba(0, 255, 255, 0.6);
    --muted: rgba(255, 255, 255, 0.75);
    --red: #EF4444;
}
body{font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: linear-gradient(135deg, #0F2845 0%, #1A3A5A 100%); color:var(--text); display:grid; place-items:center; height:100vh; margin:0;}
.card{background: linear-gradient(135deg, var(--card) 0%, rgba(30, 58, 95, 0.95) 100%); border:2px solid rgba(0, 255, 255, 0.4); border-radius:16px; padding:32px; width:420px; max-width:90vw; box-shadow:0 8px 32px rgba(0,0,0,0.5), 0 0 40px rgba(0,255,255,0.2);}
.login-vehicle-image{width:100%; max-width:320px; height:auto; margin:0 auto 20px; display:block; filter:drop-shadow(0 0 20px rgba(0,255,255,0.4)); border-radius:8px; object-fit:contain;}
.card h2{font-size:24px; font-weight:700; color:var(--cyan); text-align:center; margin-bottom:8px; text-shadow:0 0 15px var(--cyan-glow);}
.card .subtitle{text-align:center; color:var(--muted); font-size:13px; margin-bottom:24px;}
input{width:100%; padding:12px 16px; margin:8px 0; border-radius:10px; border:1px solid rgba(0,255,255,0.35); background:rgba(15,40,69,0.7); color:var(--text); font-size:14px; font-family:inherit; transition:all 0.2s;}
input:focus{outline:none; border-color:var(--cyan); box-shadow:0 0 15px rgba(0,255,255,0.4); background:rgba(15,40,69,0.85);}
button{width:100%; padding:12px; border-radius:10px; border:none; background:linear-gradient(135deg, var(--cyan) 0%, #00CCCC 100%); color:#0F2845; font-weight:700; font-size:14px; cursor:pointer; transition:all 0.2s; box-shadow:0 4px 12px rgba(0,255,255,0.4);}
button:hover{transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,255,255,0.5); background:linear-gradient(135deg, #00FFFF 0%, #00DDDD 100%);}
a{color:var(--cyan); text-decoration:none}
.muted{color:var(--muted); font-size:12px;}
.login-hint{text-align:center; color:var(--muted); font-size:12px; margin-top:16px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.1);}
</style></head>
<body>
  <div class="card">
    <img src="/static/rover4.webp" alt="Autonomous Rover" class="login-vehicle-image" onerror="this.style.display='none'">
    <h2>🚀 Astra Dashboard</h2>
    <div class="subtitle">Project Astra NZ - V9</div>
    <form method="post" action="/login">
      <input name="username" placeholder="Username" required autocomplete="username">
      <input name="password" type="password" placeholder="Password" required autocomplete="current-password">
      <button type="submit">Sign In</button>
    </form>
    <div class="login-hint">Developed by Harinder Singh</div>
    <div class="muted" style="margin-top:10px; text-align:center;"><a href="/signup">Request admin signup</a></div>
  </div>
</body></html>
'''

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        user = request.form.get('username','')
        pw = request.form.get('password','')
        if users.get(user) == pw or (user=='admin' and pw=='admin'):
            session['user'] = user
            return redirect('/')
        return render_template_string(LOGIN_HTML)
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

SIGNUP_HTML = '''
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signup - Astra Dashboard</title>
<style>body{font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0f1115; color:#e6eaf2; display:grid; place-items:center; height:100vh;} .card{background:#181c26; border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:24px; width:340px; box-shadow:0 8px 24px rgba(0,0,0,0.35)} input{width:100%; padding:10px 12px; margin:8px 0; border-radius:10px; border:1px solid rgba(255,255,255,0.12); background:#10141c; color:#e6eaf2} button{width:100%; padding:10px 12px; border-radius:10px; border:1px solid rgba(255,255,255,0.12); background:#6ee7b7; color:#0f1115; font-weight:700; cursor:pointer} .muted{color:#98a2b3; font-size:12px;}</style></head>
<body>
  <div class="card">
    <h3 style="margin:0 0 12px 0;">Admin Signup</h3>
    <form method="post" action="/signup">
      <input name="secret" placeholder="Secret Code" required>
      <input name="username" placeholder="New Admin Username" required>
      <input name="password" type="password" placeholder="New Admin Password" required>
      <button type="submit">Create Admin</button>
    </form>
    <div class="muted" style="margin-top:10px;">A valid secret code is required.</div>
  </div>
</body></html>
'''

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        secret = request.form.get('secret','')
        if secret != SIGNUP_SECRET:
            return render_template_string(SIGNUP_HTML)
        users = load_users()
        user = request.form.get('username','')
        pw = request.form.get('password','')
        if user:
            users[user] = pw
            save_users(users)
            return redirect('/login')
    return render_template_string(SIGNUP_HTML)

@app.route('/static/rover4.webp')
def serve_rover_image():
    """Serve the rover image for login page"""
    from flask import send_from_directory
    import os
    rover_path = os.path.join(os.path.dirname(__file__), 'rover4.webp')
    if os.path.exists(rover_path):
        return send_from_directory(os.path.dirname(rover_path), 'rover4.webp')
    return "Image not found", 404

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

@app.route('/api/crop/image/<int:slot>')
def get_crop_image(slot):
    """Serve a specific slot from the rolling buffer (1-10)"""
    from flask import send_file, Response
    import os
    import io
    import glob
    from PIL import Image, ImageDraw, ImageFont
    
    # Validate slot number
    if slot < 1 or slot > 10:
        slot = 1
    
    image_path = f"/tmp/rover_vision/{slot}.jpg"
    
    # Try the rolling buffer first
    if os.path.exists(image_path):
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            
            response = Response(img_data, mimetype='image/jpeg')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        except Exception as e:
            print(f"Error reading crop image slot {slot}: {e}")
    
    # Fallback: try to get the latest image from archive
    try:
        archive_images = sorted(glob.glob('/tmp/crop_archive/crop_*.jpg'), reverse=True)
        if archive_images:
            with open(archive_images[0], 'rb') as f:
                img_data = f.read()
            
            response = Response(img_data, mimetype='image/jpeg')
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
    except Exception as e:
        print(f"Error reading archive image: {e}")
    
    # If all else fails, create a placeholder image
    try:
        # Create a 640x480 placeholder image
        img = Image.new('RGB', (640, 480), color='black')
        draw = ImageDraw.Draw(img)
        
        # Add text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        text = f"ROVER VISION\nSlot {slot} loading..."
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

@app.route('/api/crop/latest')
def get_crop_latest():
    """Serve the most recent image from rolling buffer or archive"""
    from flask import Response
    import glob
    try:
        # Prefer the most recently modified file in /tmp/rover_vision
        vision_files = sorted(glob.glob('/tmp/rover_vision/*.jpg'), key=os.path.getmtime, reverse=True)
        if vision_files:
            with open(vision_files[0], 'rb') as f:
                data = f.read()
            resp = Response(data, mimetype='image/jpeg')
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            return resp
        # Fallback to crop archive
        archive_files = sorted(glob.glob('/tmp/crop_archive/crop_*.jpg'), reverse=True)
        if archive_files:
            with open(archive_files[0], 'rb') as f:
                data = f.read()
            resp = Response(data, mimetype='image/jpeg')
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            return resp
    except Exception as e:
        print(f"Error serving latest crop image: {e}")
    return "No latest image", 404

def mjpeg_generator(shared_image_path: str):
    import time
    last_mtime = 0
    while True:
        try:
            if os.path.exists(shared_image_path):
                mtime = os.path.getmtime(shared_image_path)
                if mtime != last_mtime:
                    # Read bytes and encode to ensure robust streaming
                    with open(shared_image_path, 'rb') as f:
                        data = f.read()
                    # Send as-is if already JPEG
                    frame = data
                    last_mtime = mtime
                else:
                    frame = None
            else:
                frame = None
        except Exception:
            frame = None

        if frame is not None:
            try:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception:
                pass
        time.sleep(0.066)  # ~15 fps

@app.route('/api/stream')
def api_stream():
    """MJPEG stream directly from shared RealSense frame without camera access."""
    from flask import Response
    shared = '/tmp/vision_v9/rgb_latest.jpg'
    if not os.path.exists(shared):
        return "No stream source", 404
    return Response(mjpeg_generator(shared), mimetype='multipart/x-mixed-replace; boundary=frame')

# Additional streams: depth (pseudo-color) and IR (mono)
@app.route('/api/stream/depth')
def api_stream_depth():
    from flask import Response
    shared = '/tmp/vision_v9/depth_latest.jpg'
    if not os.path.exists(shared):
        return "No depth stream", 404
    return Response(mjpeg_generator(shared), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stream/ir')
def api_stream_ir():
    from flask import Response
    shared = '/tmp/vision_v9/ir_latest.jpg'
    if not os.path.exists(shared):
        return "No IR stream", 404
    return Response(mjpeg_generator(shared), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/crop/gallery')
def crop_gallery():
    """Simple gallery page to browse crop images"""
    import glob
    files = sorted(glob.glob('/tmp/crop_archive/crop_*.jpg'), key=os.path.getmtime, reverse=True)
    items = []
    for fp in files[:300]:
        name = os.path.basename(fp)
        ts = os.path.getmtime(fp)
        tstr = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        items.append(f'<div style="display:inline-block; margin:8px; text-align:center;">\
            <a href="/api/crop/archive/{name}" target="_blank">\
              <img src="/api/crop/archive/{name}" style="width:220px; height:140px; object-fit:cover; border:1px solid #333; border-radius:8px; display:block;">\
            </a>\
            <div style="color:#98a2b3; font: 12px system-ui; margin-top:4px;">{tstr}</div>\
        </div>')
    grid = ''.join(items) if items else '<p>No images yet.</p>'
    return f"""
    <html>
    <head><title>Crop Gallery</title></head>
    <body style="background:#0f1115; color:#e6eaf2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial; padding: 24px;">
      <h2 style="margin:0 0 12px 0;">Crop Gallery</h2>
      <div><a href="/" style="color:#6ee7b7; text-decoration:none;">← Back to Dashboard</a></div>
      <div style="display:flex; flex-wrap:wrap; margin-top:16px;">{grid}</div>
    </body>
    </html>
    """

@app.route('/api/crop/archive/<path:filename>')
def serve_archive_file(filename):
    """Serve a specific archived image safely from /tmp/crop_archive"""
    from flask import send_file, abort, Response
    safe_dir = '/tmp/crop_archive'
    full_path = os.path.join(safe_dir, os.path.basename(filename))
    if not os.path.exists(full_path):
        return abort(404)
    try:
        with open(full_path, 'rb') as f:
            data = f.read()
        resp = Response(data, mimetype='image/jpeg')
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        print(f"Error serving archive file: {e}")
        return abort(404)

@app.route('/api/crop/list')
def crop_list():
    """Return JSON list of archived images with timestamps"""
    import glob
    files = sorted(glob.glob('/tmp/crop_archive/crop_*.jpg'), key=os.path.getmtime, reverse=True)
    out = []
    for fp in files[:300]:
        ts = os.path.getmtime(fp)
        out.append({
            'filename': os.path.basename(fp),
            'name': os.path.basename(fp),
            'url': f"/api/crop/archive/{os.path.basename(fp)}",
            'time': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
            'mtime': int(ts)
        })
    return jsonify({'images': out})

@app.route('/api/crop/status')
def get_crop_status():
    """Get crop monitor status"""
    import os
    import json
    import time
    
    status_file = "/tmp/crop_monitor_v9.json"
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
            with open('/tmp/proximity_v9.json', 'r') as f:
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
                    crop_status_file = "/tmp/crop_monitor_v9.json"
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
        print("Reading telemetry from /tmp/proximity_v9.json")
        data_thread = threading.Thread(target=read_telemetry_file, daemon=True)

    data_thread.start()

    # Choose an available port (prefer 8081)
    preferred_port = int(os.environ.get('ASTRA_DASHBOARD_PORT', '8081'))
    port = preferred_port
    for _ in range(5):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(('0.0.0.0', port)) != 0:
                break
        port += 1

    # Start Flask server
    print("\n" + "="*50)
    print("PROJECT ASTRA NZ - Telemetry Dashboard V9")
    print("="*50)
    print(f"Dashboard (Local): http://0.0.0.0:{port}")
    print(f"API Endpoint: http://0.0.0.0:{port}/api/telemetry")
    print("="*50 + "\n")

    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except OSError as e:
        print(f"[ERROR] Failed to start server: {e}")
