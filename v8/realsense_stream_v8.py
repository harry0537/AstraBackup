#!/usr/bin/env python3
"""
Project Astra NZ - RealSense MJPEG Streamer V8
Provides live MJPEG video stream from RealSense camera for dashboard
Component 199 - Real-time video streaming
"""

import cv2
import numpy as np
import time
import threading
from flask import Flask, Response
import os

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False
    print("ERROR: pyrealsense2 not available")

# Configuration
COMPONENT_ID = 199
STREAM_PORT = 8082
STREAM_FPS = 15  # Target FPS for stream
STREAM_QUALITY = 80  # JPEG quality for stream

app = Flask(__name__)

class RealSenseStreamer:
    def __init__(self):
        self.pipeline = None
        self.running = True
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_count = 0
        
    def connect_camera(self):
        """Connect to RealSense camera"""
        try:
            if not REALSENSE_AVAILABLE:
                print("✗ RealSense library not available")
                return False
                
            print("Connecting to RealSense for streaming...")
            self.pipeline = rs.pipeline()
            config = rs.config()
            
            # Stream configurations to try (prefer higher res for viewing)
            configs_to_try = [
                (rs.stream.color, 848, 480, rs.format.bgr8, 30),
                (rs.stream.color, 640, 480, rs.format.bgr8, 30),
                (rs.stream.color, 640, 360, rs.format.bgr8, 30),
                (rs.stream.color, 424, 240, rs.format.bgr8, 30),
            ]
            
            for i, (stream, width, height, format, fps) in enumerate(configs_to_try):
                try:
                    print(f"  Trying {width}x{height} @ {fps}fps...")
                    config = rs.config()
                    config.enable_stream(stream, width, height, format, fps)
                    self.pipeline.start(config)
                    
                    # Test frame capture
                    frames = self.pipeline.wait_for_frames(timeout_ms=2000)
                    color_frame = frames.get_color_frame()
                    if color_frame:
                        print(f"✓ RealSense streaming - {width}x{height} @ {fps}fps")
                        return True
                    else:
                        self.pipeline.stop()
                        time.sleep(0.5)
                except Exception as e:
                    print(f"  Config {i+1} failed: {e}")
                    if self.pipeline:
                        try:
                            self.pipeline.stop()
                        except:
                            pass
                    time.sleep(0.5)
                    continue
            
            print("✗ All RealSense configurations failed")
            self.pipeline = None
            return False
            
        except Exception as e:
            print(f"✗ RealSense connection failed: {e}")
            self.pipeline = None
            return False
    
    def capture_thread(self):
        """Background thread to continuously capture frames"""
        while self.running:
            if not self.pipeline:
                time.sleep(0.5)
                continue
                
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=100)
                color_frame = frames.get_color_frame()
                
                if color_frame:
                    # Convert to numpy array
                    image = np.asanyarray(color_frame.get_data())
                    
                    with self.frame_lock:
                        self.latest_frame = image
                        self.frame_count += 1
                        
            except Exception as e:
                # Silent fail for dropped frames
                time.sleep(0.01)
                
    def generate_mjpeg(self):
        """Generate MJPEG stream"""
        while self.running:
            with self.frame_lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                else:
                    # Create placeholder frame
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Waiting for camera...", (150, 240),
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, 
                                      [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])
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
        print(f"Stream FPS: {STREAM_FPS}")
        print(f"JPEG quality: {STREAM_QUALITY}")
        print("=" * 60)
        
        if not self.connect_camera():
            print("✗ Cannot start without camera")
            return
        
        # Start capture thread
        capture_thread = threading.Thread(target=self.capture_thread, daemon=True)
        capture_thread.start()
        print("✓ Capture thread started")
        
        print(f"\n✓ RealSense streamer operational")
        print(f"  • Stream URL: http://0.0.0.0:{STREAM_PORT}/stream")
        print(f"  • Resolution: Auto-detected")
        print(f"  • Frame rate: ~{STREAM_FPS} FPS")
        print()
        
        try:
            # Start Flask server
            app.run(host='0.0.0.0', port=STREAM_PORT, threaded=True, debug=False)
        except KeyboardInterrupt:
            print("\n\nShutting down streamer...")
        finally:
            self.running = False
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
            print("✓ RealSense streamer stopped")

# Flask routes
streamer = RealSenseStreamer()

@app.route('/')
def index():
    """Simple status page"""
    status = "RUNNING" if streamer.pipeline else "NO CAMERA"
    return f"""
    <html>
    <head><title>RealSense Stream</title></head>
    <body style="background: #000; color: #0f0; font-family: monospace; text-align: center; padding: 50px;">
        <h1>RealSense MJPEG Stream</h1>
        <p>Status: {status}</p>
        <p>Frames captured: {streamer.frame_count}</p>
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

