#!/usr/bin/env python3
"""
Project Astra NZ - RealSense MJPEG Streamer V8
Provides live MJPEG video stream from proximity bridge's RealSense frames
Component 199 - Real-time video streaming (NO camera conflict)
"""

import cv2
import numpy as np
import time
import threading
from flask import Flask, Response
import os

# Configuration
COMPONENT_ID = 199
STREAM_PORT = 8082
STREAM_FPS = 15  # Target FPS for stream
SHARED_IMAGE = "/tmp/realsense_latest.jpg"  # Shared from proximity bridge

app = Flask(__name__)

class RealSenseStreamer:
    def __init__(self):
        self.running = True
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_count = 0
        self.last_modified = 0
        
    def check_shared_frames(self):
        """Check if proximity bridge is sharing frames"""
        if os.path.exists(SHARED_IMAGE):
            print(f"✓ Found shared RealSense frames at {SHARED_IMAGE}")
            return True
        else:
            print(f"⚠ Waiting for proximity bridge to share frames...")
            print(f"  Proximity bridge will create {SHARED_IMAGE}")
            return False
    
    def capture_thread(self):
        """Background thread to read shared frames from proximity bridge"""
        while self.running:
            try:
                # Check if shared image file exists and has been updated
                if os.path.exists(SHARED_IMAGE):
                    current_modified = os.path.getmtime(SHARED_IMAGE)
                    
                    # Only read if file has been updated
                    if current_modified != self.last_modified:
                        frame = cv2.imread(SHARED_IMAGE)
                        
                        if frame is not None:
                            with self.frame_lock:
                                self.latest_frame = frame
                                self.frame_count += 1
                                self.last_modified = current_modified
                
                time.sleep(1.0 / STREAM_FPS)  # Control read rate
                        
            except Exception as e:
                # Silent fail for read errors
                time.sleep(0.1)
                
    def generate_mjpeg(self):
        """Generate MJPEG stream"""
        while self.running:
            with self.frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                else:
                    # Create placeholder frame
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Waiting for proximity bridge...", (100, 240),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Frame is already JPEG compressed, just read and send
            if os.path.exists(SHARED_IMAGE):
                try:
                    with open(SHARED_IMAGE, 'rb') as f:
                        frame_bytes = f.read()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                except:
                    # Fallback to encoded frame if file read fails
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # No shared image available yet
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Control frame rate
            time.sleep(1.0 / STREAM_FPS)
    
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("RealSense MJPEG Streamer V8 - Component 199")
        print("=" * 60)
        print(f"Stream port: {STREAM_PORT}")
        print(f"Stream FPS: ~{STREAM_FPS}")
        print(f"Shared frames: {SHARED_IMAGE}")
        print("=" * 60)
        
        # Check if proximity bridge is sharing frames
        self.check_shared_frames()
        
        # Start capture thread
        capture_thread = threading.Thread(target=self.capture_thread, daemon=True)
        capture_thread.start()
        print("✓ Frame reader thread started")
        
        print(f"\n✓ RealSense streamer operational")
        print(f"  • Stream URL: http://0.0.0.0:{STREAM_PORT}/stream")
        print(f"  • Source: Proximity bridge shared frames")
        print(f"  • Frame rate: ~{STREAM_FPS} FPS")
        print(f"  • NO camera conflict - using shared frames")
        print()
        
        try:
            # Start Flask server
            app.run(host='0.0.0.0', port=STREAM_PORT, threaded=True, debug=False)
        except KeyboardInterrupt:
            print("\n\nShutting down streamer...")
        finally:
            self.running = False
            print("✓ RealSense streamer stopped")

# Flask routes
streamer = RealSenseStreamer()

@app.route('/')
def index():
    """Simple status page"""
    status = "RUNNING" if os.path.exists(SHARED_IMAGE) else "WAITING FOR PROXIMITY BRIDGE"
    return f"""
    <html>
    <head><title>RealSense Stream</title></head>
    <body style="background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px;">
        <h1>RealSense MJPEG Stream (Shared Frames)</h1>
        <p>Status: {status}</p>
        <p>Frames served: {streamer.frame_count}</p>
        <p>Source: Proximity Bridge ({SHARED_IMAGE})</p>
        <p>Stream URL: <a href="/stream" style="color: #0ff;">/stream</a></p>
        <img src="/stream" style="max-width: 90%; border: 2px solid #0f0;">
    </body>
    </html>
    """

@app.route('/stream')
def video_feed():
    """MJPEG stream endpoint"""
    return Response(streamer.generate_mjpeg(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    streamer.run()

