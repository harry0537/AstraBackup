#!/usr/bin/env python3
"""
Project Astra NZ - Row Following System (Component 196)
Computer vision-based crop row detection and navigation
"""

import cv2
import numpy as np
import time
from pymavlink import mavutil
import pyrealsense2 as rs
import threading

# Configuration (NEVER MODIFY)
PIXHAWK_PORT = '/dev/serial/by-id/usb-Holybro_Pixhawk6C_1C003C000851333239393235-if00'
PIXHAWK_BAUD = 57600
COMPONENT_ID = 196

class RowFollowingSystem:
    def __init__(self):
        self.mavlink = None
        self.pipeline = None
        self.running = True
        
        # Navigation state
        self.row_detected = False
        self.lateral_offset = 0.0  # meters from center
        self.heading_error = 0.0   # degrees
        self.confidence = 0.0
        
        # HSV range for green vegetation (adjustable)
        self.hsv_lower = np.array([35, 40, 40])
        self.hsv_upper = np.array([85, 255, 255])
        
        # Statistics
        self.stats = {
            'frames_processed': 0,
            'rows_detected': 0,
            'commands_sent': 0
        }
        
    def connect_pixhawk(self):
        """Connect to Pixhawk for navigation commands"""
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
            
    def connect_camera(self):
        """Connect to RealSense camera for row detection"""
        try:
            print("Connecting to RealSense for row detection")
            self.pipeline = rs.pipeline()
            config = rs.config()
            
            # RGB stream for row detection
            config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
            
            self.pipeline.start(config)
            
            # Test frames
            for _ in range(5):
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                if frames.get_color_frame():
                    print("✓ Camera connected for row detection")
                    return True
                    
            return False
            
        except Exception as e:
            print(f"✗ Camera connection failed: {e}")
            return False
            
    def detect_rows(self, image):
        """Detect crop rows in image"""
        height, width = image.shape[:2]
        
        # Convert to HSV for vegetation detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create mask for green vegetation
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        
        # Noise reduction
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Focus on bottom 2/3 of image (closer to rover)
        roi_start = height // 3
        roi = mask[roi_start:, :]
        
        # Find contours
        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) < 2:
            return False, 0, 0
            
        # Sort contours by area
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        # Find two main row regions
        rows = []
        for contour in contours[:2]:
            # Fit a line to each contour
            if len(contour) > 5:
                [vx, vy, x, y] = cv2.fitLine(contour, cv2.DIST_L2, 0, 0.01, 0.01)
                rows.append((vx, vy, x, y))
                
        if len(rows) < 2:
            return False, 0, 0
            
        # Calculate center line between rows
        row1_x = rows[0][2]
        row2_x = rows[1][2]
        center_x = (row1_x + row2_x) / 2
        
        # Calculate lateral offset (pixels to meters approximation)
        image_center_x = width / 2
        pixel_offset = center_x - image_center_x
        lateral_offset = pixel_offset * 0.002  # Approximate scaling
        
        # Calculate heading error from row angles
        angle1 = np.arctan2(rows[0][1], rows[0][0]) * 180 / np.pi
        angle2 = np.arctan2(rows[1][1], rows[1][0]) * 180 / np.pi
        heading_error = (angle1 + angle2) / 2
        
        return True, lateral_offset, heading_error
        
    def send_navigation_command(self):
        """Send steering corrections to Pixhawk"""
        if not self.mavlink or not self.row_detected:
            return
            
        # Calculate steering adjustment
        # Positive offset = rows are to the right, need to steer right
        # Negative offset = rows are to the left, need to steer left
        
        steer_gain = 0.5
        heading_gain = 0.3
        
        steering_cmd = (self.lateral_offset * steer_gain + 
                       self.heading_error * heading_gain)
        
        # Clamp steering command
        steering_cmd = max(-1.0, min(1.0, steering_cmd))
        
        # Send as RC override (channel 1 = steering)
        # Center = 1500, range 1000-2000
        steering_pwm = int(1500 + steering_cmd * 500)
        
        self.mavlink.mav.rc_channels_override_send(
            self.mavlink.target_system,
            self.mavlink.target_component,
            steering_pwm,  # Channel 1 - Steering
            0,            # Channel 2
            0,            # Channel 3 
            0,            # Channel 4
            0, 0, 0, 0,   # Channels 5-8
            0, 0, 0, 0, 0, 0, 0, 0,  # Channels 9-16
            0, 0          # Channels 17-18
        )
        
        self.stats['commands_sent'] += 1
        
    def vision_thread(self):
        """Thread for image processing"""
        while self.running:
            if not self.pipeline:
                time.sleep(1)
                continue
                
            try:
                # Get frame
                frames = self.pipeline.wait_for_frames(timeout_ms=100)
                color_frame = frames.get_color_frame()
                
                if color_frame:
                    # Convert to numpy array
                    image = np.asanyarray(color_frame.get_data())
                    
                    # Detect rows
                    detected, offset, heading = self.detect_rows(image)
                    
                    self.row_detected = detected
                    self.lateral_offset = offset
                    self.heading_error = heading
                    
                    if detected:
                        self.stats['rows_detected'] += 1
                        self.confidence = min(1.0, self.confidence + 0.1)
                    else:
                        self.confidence = max(0.0, self.confidence - 0.2)
                        
                    self.stats['frames_processed'] += 1
                    
            except Exception as e:
                # Silent fail for vision processing
                pass
                
    def print_status(self):
        """Print navigation status"""
        if self.row_detected:
            status = "ROWS DETECTED"
            offset_str = f"{self.lateral_offset:+.2f}m"
            heading_str = f"{self.heading_error:+.1f}°"
        else:
            status = "SEARCHING"
            offset_str = "---"
            heading_str = "---"
            
        detection_rate = 0
        if self.stats['frames_processed'] > 0:
            detection_rate = (self.stats['rows_detected'] / 
                            self.stats['frames_processed']) * 100
            
        print(f"\r[{status:15s}] Offset: {offset_str:8s} | "
              f"Heading: {heading_str:7s} | "
              f"Confidence: {self.confidence:.1%} | "
              f"Detection: {detection_rate:.1f}% | "
              f"Cmds: {self.stats['commands_sent']:4d}", end='')
              
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Row Following System - Component 196")
        print("=" * 60)
        
        # Connect systems
        pixhawk_ok = self.connect_pixhawk()
        camera_ok = self.connect_camera()
        
        if not camera_ok:
            print("❌ Cannot operate without camera")
            return
            
        if not pixhawk_ok:
            print("⚠ Running in vision-only mode (no Pixhawk)")
            
        # Start vision thread
        vision_thread = threading.Thread(target=self.vision_thread)
        vision_thread.daemon = True
        vision_thread.start()
        
        print("\n✓ Row following system operational")
        print("  • Processing at 30 fps")
        print("  • Detecting green vegetation rows")
        print("  • Sending steering corrections\n")
        
        # Main loop
        try:
            last_command = time.time()
            last_status = time.time()
            
            while self.running:
                # Send commands at 2Hz when rows detected
                if time.time() - last_command > 0.5:
                    if self.row_detected and self.confidence > 0.3:
                        self.send_navigation_command()
                    last_command = time.time()
                    
                # Update status at 2Hz
                if time.time() - last_status > 0.5:
                    self.print_status()
                    last_status = time.time()
                    
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\nShutting down row following...")
            
        finally:
            self.running = False
            
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
                    
            print("✓ Row following stopped")

if __name__ == "__main__":
    system = RowFollowingSystem()
    system.run()