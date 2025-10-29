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
        :root {
            --bg: #0f1115;
            --bg-elev: #151922;
            --card: #181c26;
            --card-border: rgba(255,255,255,0.06);
            --text: #e6eaf2;
            --muted: #98a2b3;
            --accent: #6ee7b7; /* mint */
            --accent-strong: #34d399;
            --ok: #22c55e;
            --warn: #f59e0b;
            --error: #ef4444;
            --chip: rgba(255,255,255,0.06);
            --chip-border: rgba(255,255,255,0.08);
            --shadow: 0 8px 24px rgba(0,0,0,0.35);
            --radius: 14px;
            --radius-sm: 10px;
        }
        /* Sport variant (inspired by red cluster rings) */
        html[data-theme="sport"] {
            --accent: #fb7185; /* rose */
            --accent-strong: #f43f5e;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji";
            background: 
                        radial-gradient(1200px 600px at 20% -10%, rgba(52, 211, 153, 0.08), transparent 60%),
                        radial-gradient(1400px 700px at 120% 10%, rgba(99, 102, 241, 0.06), transparent 60%),
                        repeating-linear-gradient(0deg, rgba(255,255,255,0.03) 0px, rgba(255,255,255,0.03) 1px, transparent 1px, transparent 24px),
                        repeating-linear-gradient(90deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, transparent 1px, transparent 24px),
                        var(--bg);
            color: var(--text);
            padding: 24px;
        }
        .header {
            max-width: 1200px;
            margin: 0 auto 24px auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
        }
        .header h1 {
            font-size: 18px;
            letter-spacing: 0.08em;
            font-weight: 700;
        }
        #timestamp {
            background: rgba(255,255,255,0.06);
            color: var(--text);
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            border: 1px solid var(--card-border);
        }
        .actions {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .btn {
            padding: 6px 10px;
            border-radius: 10px;
            border: 1px solid var(--card-border);
            background: var(--chip);
            color: var(--text);
            font-size: 12px;
            cursor: pointer;
        }
        .btn:hover { filter: brightness(1.1); }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        /* Indicator ribbon */
        .ribbon {
            max-width: 1200px;
            margin: 0 auto 16px auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }
        .light {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: var(--radius-sm);
            box-shadow: var(--shadow);
            font-size: 12px;
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
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            padding: 18px;
            box-shadow: var(--shadow);
            position: relative;
            overflow: hidden;
        }
        .panel:before {
            content: "";
            position: absolute;
            inset: -1px;
            border-radius: inherit;
            background: linear-gradient(120deg, rgba(255,255,255,0.06), transparent 40%, var(--accent) 50%, transparent 60%, rgba(255,255,255,0.06));
            filter: blur(8px);
            opacity: 0.35;
            pointer-events: none;
        }
        .panel h2 {
            font-size: 14px;
            margin-bottom: 12px;
            color: var(--text);
            font-weight: 700;
            letter-spacing: 0.06em;
        }
        .radar-container {
            position: relative;
            width: 280px;
            height: 280px;
            margin: 0 auto;
            border-radius: 50%;
            border: 1px solid var(--card-border);
            background: radial-gradient(50% 50% at 50% 50%, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 60%, transparent 100%);
            box-shadow: inset 0 0 40px rgba(0,0,0,0.6);
        }
        .radar-container:after {
            content: "";
            position: absolute;
            inset: -6px;
            border-radius: 50%;
            background: conic-gradient(from 0deg, transparent 0deg, rgba(255,255,255,0.0) 260deg, var(--accent) 300deg, transparent 360deg);
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
        .status-grid {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 10px;
            font-size: 14px;
        }
        .status-label {
            color: var(--muted);
        }
        .status-value {
            text-align: right;
            justify-self: end;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid var(--card-border);
            background: var(--chip);
        }
        .status-ok { color: var(--ok); background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.18); }
        .status-warning { color: var(--warn); background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.18); }
        .status-error { color: var(--error); background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.18); }
        .proximity-values {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        .proximity-item {
            text-align: center;
            padding: 10px 8px;
            background: var(--chip);
            border: 1px solid var(--chip-border);
            border-radius: var(--radius-sm);
        }
        .proximity-label {
            font-size: 10px;
            color: var(--muted);
            letter-spacing: 0.06em;
        }
        .proximity-value {
            font-size: 16px;
            font-weight: 700;
        }
        .safe { color: var(--ok); }
        .warning { color: var(--warn); }
        .danger { color: var(--error); }
        .crop-image-container {
            text-align: center;
            margin-top: 10px;
        }
        .crop-image-container img {
            max-width: 100%;
            height: auto;
            max-height: 500px;
            border: 1px solid var(--card-border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }
        .crop-image-container img:hover {
            box-shadow: 0 12px 28px rgba(0,0,0,0.45);
            transform: scale(1.015);
        }
        .crop-status {
            margin-top: 15px;
            font-size: 14px;
            color: var(--muted);
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .rover-vision-container .panel {
            padding: 25px;
        }
        .rover-vision-container h2 {
            font-size: 16px;
            text-align: center;
            margin-bottom: 16px;
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
            .vision-row { grid-template-columns: 1fr; }
            .proximity-panel, .rover-vision-panel { grid-column: 1; }
            .radar-container { width: 240px; height: 240px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>PROJECT ASTRA NZ — TELEMETRY DASHBOARD V8</h1>
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
                         onerror="this.style.display='none'; document.getElementById('vision-offline').style.display='block';"
                         onload="this.style.display='block'; document.getElementById('vision-offline').style.display='none';">
                    <div id="vision-offline" class="alert-offline">
                        Rover vision offline - Crop monitor not running
                    </div>
                    <div class="crop-status" id="crop-status">
                        Rolling buffer: Slot <span id="current-slot">1</span>/10 (cycles every 3s)
                        <br><small><a href="/api/crop/status" target="_blank" style="color: var(--accent); text-decoration: none;">Debug: Check crop status</a></small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Rolling buffer system - cycle through slots 1-10 every 6 seconds
        const roverVisionImg = document.getElementById('rover-vision');
        let currentSlot = 1;
        
        function refreshRoverVision() {
            // Cycle through slots 1-10
            const newSrc = `/api/crop/image/${currentSlot}`;
            roverVisionImg.src = newSrc;
            console.log(`Loading rover vision slot ${currentSlot} at ${new Date().toLocaleTimeString()}`);
            
            // Update slot display
            document.getElementById('current-slot').textContent = currentSlot;
            
            // Advance to next slot (1-10 rolling)
            currentSlot = (currentSlot % 10) + 1;
        }
        
        // Handle image load errors
        roverVisionImg.onerror = function() {
            console.log(`Slot ${currentSlot-1} failed to load, trying next...`);
            // Try next slot immediately
            setTimeout(refreshRoverVision, 500);
        };
        
        // Handle successful image load
        roverVisionImg.onload = function() {
            console.log(`Slot ${currentSlot-1} loaded successfully`);
        };
        
        // Initial load and set up rolling timer
        refreshRoverVision();
        setInterval(refreshRoverVision, 3000); // Cycle every 3 seconds (faster to see updates)
        
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
                
                // Update ribbon lights
                const sys = data.system_status || {};
                const sen = data.sensor_health || {};
                setLight('light-proximity', sys.proximity_bridge === 'RUNNING' ? 'ok' : sys.proximity_bridge === 'STOPPED' ? 'err' : 'warn');
                setLight('light-relay', sys.data_relay === 'RUNNING' ? 'ok' : 'warn');
                setLight('light-crop', sys.crop_monitor === 'RUNNING' ? 'ok' : sys.crop_monitor === 'STOPPED' ? 'err' : 'warn');
                setLight('light-lidar', sen.rplidar === 'Good' ? 'ok' : sen.rplidar === 'Warning' ? 'warn' : 'err');
                setLight('light-realsense', sen.realsense === 'Connected' ? 'ok' : 'err');
                setLight('light-pixhawk', sen.pixhawk === 'Connected' ? 'ok' : 'warn');

                // Update crop monitor
                if (data.crop_monitor) {
                    updateCropMonitor(data.crop_monitor);
                }

                // Update timestamp
                document.getElementById('timestamp').textContent =
                    new Date().toLocaleTimeString();
                
                // Update header metrics
                const stats = data.statistics || {};
                const uptimeSecs = Number(stats.uptime) || 0;
                const h = Math.floor(uptimeSecs / 3600).toString().padStart(2,'0');
                const m = Math.floor((uptimeSecs % 3600)/60).toString().padStart(2,'0');
                const s = Math.floor(uptimeSecs % 60).toString().padStart(2,'0');
                document.getElementById('metric-uptime').textContent = `Uptime: ${h}:${m}:${s}`;
                document.getElementById('metric-fps').textContent = `FPS: ${stats.realsense_fps || 0}`;
                document.getElementById('metric-msg').textContent = `Msgs: ${stats.messages_sent || 0}`;
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }

        // Initial draw
        drawRadar([2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]);

        // Update every 1 second
        setInterval(updateDashboard, 1000);

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
