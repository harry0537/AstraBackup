#!/usr/bin/env python3
"""
Project Astra NZ - Crop Monitoring System (Component 198)
Automated crop health assessment and image capture
"""

import cv2
import numpy as np
import time
import os
from datetime import datetime
import pyrealsense2 as rs
import threading
import json

# Configuration
COMPONENT_ID = 198
IMAGE_DIR = "/home/pi/crop_images"
TEMP_IMAGE = "/tmp/crop_latest.jpg"
TRIGGER_FILE = "/tmp/crop_trigger"

class CropMonitoringSystem:
    def __init__(self):
        self.pipeline = None
        self.running = True
        
        # Ensure directories exist
        os.makedirs(IMAGE_DIR, exist_ok=True)
        os.makedirs("/tmp", exist_ok=True)
        
        # Monitoring state
        self.capture_interval = 600  # 10 minutes default
        self.last_capture = 0
        self.total_captures = 0
        
        # Analysis results
        self.latest_analysis = {
            'timestamp': None,
            'health_score': 0,
            'maturity_stage': 'unknown',
            'vegetation_index': 0,
            'anomalies': []
        }
        
    def connect_camera(self):
        """Connect to RealSense camera"""
        try:
            print("Connecting to RealSense for crop monitoring")
            self.pipeline = rs.pipeline()
            config = rs.config()
            
            # High-res color stream for crop analysis
            config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
            
            self.pipeline.start(config)
            
            # Test frames
            for _ in range(5):
                frames = self.pipeline.wait_for_frames(timeout_ms=1000)
                if frames.get_color_frame():
                    print("✓ Camera connected for crop monitoring")
                    return True
                    
            return False
            
        except Exception as e:
            print(f"✗ Camera connection failed: {e}")
            return False
            
    def analyze_vegetation(self, image):
        """Analyze vegetation health using color indices"""
        # Convert to float for calculations
        img_float = image.astype(float)
        
        # Extract color channels
        b, g, r = cv2.split(img_float)
        
        # Avoid division by zero
        epsilon = 1e-6
        
        # Calculate vegetation indices
        # NGRDI (Normalized Green-Red Difference Index)
        ngrdi = np.where((g + r) > epsilon, 
                         (g - r) / (g + r + epsilon),
                         0)
        
        # GLI (Green Leaf Index)
        gli = np.where((2 * g + r + b) > epsilon,
                       (2 * g - r - b) / (2 * g + r + b + epsilon),
                       0)
        
        # VARI (Visible Atmospherically Resistant Index)
        vari = np.where((g + r - b) > epsilon,
                       (g - r) / (g + r - b + epsilon),
                       0)
        
        # Calculate mean values
        ngrdi_mean = np.mean(ngrdi)
        gli_mean = np.mean(gli)
        vari_mean = np.mean(vari)
        
        # Combine indices for overall vegetation score (0-100)
        vegetation_score = (ngrdi_mean + 1) * 25 + (gli_mean + 1) * 25 + (vari_mean + 1) * 25
        vegetation_score = max(0, min(100, vegetation_score))
        
        return vegetation_score, ngrdi_mean, gli_mean, vari_mean
        
    def detect_anomalies(self, image):
        """Detect potential issues in crops"""
        anomalies = []
        
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Check for brown/yellow areas (potential disease/stress)
        brown_lower = np.array([10, 50, 50])
        brown_upper = np.array([25, 255, 255])
        brown_mask = cv2.inRange(hsv, brown_lower, brown_upper)
        brown_ratio = np.count_nonzero(brown_mask) / brown_mask.size
        
        if brown_ratio > 0.1:  # More than 10% brown
            anomalies.append({
                'type': 'discoloration',
                'severity': 'high' if brown_ratio > 0.3 else 'medium',
                'area_percentage': brown_ratio * 100
            })
            
        # Check for sparse vegetation
        green_lower = np.array([35, 40, 40])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        green_ratio = np.count_nonzero(green_mask) / green_mask.size
        
        if green_ratio < 0.3:  # Less than 30% green
            anomalies.append({
                'type': 'sparse_vegetation',
                'severity': 'high' if green_ratio < 0.1 else 'medium',
                'coverage_percentage': green_ratio * 100
            })
            
        return anomalies
        
    def classify_maturity(self, vegetation_score, image):
        """Classify crop maturity stage"""
        # Simplified maturity classification
        # In production, use ML model or crop-specific rules
        
        if vegetation_score > 75:
            return 'vigorous_growth'
        elif vegetation_score > 60:
            return 'mature'
        elif vegetation_score > 40:
            return 'developing'
        elif vegetation_score > 20:
            return 'young'
        else:
            return 'seedling_or_stressed'
            
    def calculate_health_score(self, vegetation_score, anomalies):
        """Calculate overall crop health score"""
        health_score = vegetation_score
        
        # Reduce score based on anomalies
        for anomaly in anomalies:
            if anomaly['severity'] == 'high':
                health_score -= 20
            elif anomaly['severity'] == 'medium':
                health_score -= 10
            elif anomaly['severity'] == 'low':
                health_score -= 5
                
        return max(0, min(100, health_score))
        
    def capture_and_analyze(self, trigger_type='scheduled'):
        """Capture image and perform analysis"""
        if not self.pipeline:
            return False
            
        try:
            # Capture frame
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
            color_frame = frames.get_color_frame()
            
            if not color_frame:
                return False
                
            # Convert to numpy array
            image = np.asanyarray(color_frame.get_data())
            
            # Perform analysis
            veg_score, ngrdi, gli, vari = self.analyze_vegetation(image)
            anomalies = self.detect_anomalies(image)
            maturity = self.classify_maturity(veg_score, image)
            health_score = self.calculate_health_score(veg_score, anomalies)
            
            # Update analysis results
            self.latest_analysis = {
                'timestamp': datetime.now().isoformat(),
                'health_score': health_score,
                'maturity_stage': maturity,
                'vegetation_index': veg_score,
                'indices': {
                    'ngrdi': float(ngrdi),
                    'gli': float(gli),
                    'vari': float(vari)
                },
                'anomalies': anomalies,
                'trigger_type': trigger_type
            }
            
            # Save original image
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"crop_{trigger_type}_{timestamp}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)
            cv2.imwrite(filepath, image)
            
            # Save to temp location for relay
            cv2.imwrite(TEMP_IMAGE, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Save analysis overlay
            overlay = self.create_analysis_overlay(image)
            analysis_filename = f"analysis_{trigger_type}_{timestamp}.jpg"
            analysis_path = os.path.join(IMAGE_DIR, analysis_filename)
            cv2.imwrite(analysis_path, overlay)
            
            # Save analysis JSON
            json_filename = f"analysis_{trigger_type}_{timestamp}.json"
            json_path = os.path.join(IMAGE_DIR, json_filename)
            with open(json_path, 'w') as f:
                json.dump(self.latest_analysis, f, indent=2)
                
            self.total_captures += 1
            print(f"\n✓ Captured and analyzed image #{self.total_captures}")
            print(f"  Health: {health_score:.1f}/100 | "
                  f"Maturity: {maturity} | "
                  f"Vegetation: {veg_score:.1f}%")
                  
            if anomalies:
                print(f"  ⚠ Anomalies detected: {len(anomalies)}")
                
            return True
            
        except Exception as e:
            print(f"✗ Capture/analysis failed: {e}")
            return False
            
    def create_analysis_overlay(self, image):
        """Create image with analysis overlay"""
        overlay = image.copy()
        height, width = overlay.shape[:2]
        
        # Add text overlay
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Background for text
        cv2.rectangle(overlay, (0, 0), (width, 80), (0, 0, 0), -1)
        
        # Analysis text
        health = self.latest_analysis['health_score']
        maturity = self.latest_analysis['maturity_stage']
        veg = self.latest_analysis['vegetation_index']
        
        cv2.putText(overlay, f"Health: {health:.0f}/100", 
                   (10, 25), font, 0.7, (0, 255, 0), 2)
        cv2.putText(overlay, f"Maturity: {maturity}", 
                   (10, 50), font, 0.7, (255, 255, 0), 2)
        cv2.putText(overlay, f"Vegetation: {veg:.1f}%", 
                   (10, 75), font, 0.7, (0, 255, 255), 2)
                   
        # Timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(overlay, timestamp, 
                   (width - 250, height - 10), font, 0.5, (255, 255, 255), 1)
                   
        return overlay
        
    def check_trigger_file(self):
        """Check for external capture trigger"""
        if os.path.exists(TRIGGER_FILE):
            try:
                os.remove(TRIGGER_FILE)
                return True
            except:
                pass
        return False
        
    def monitoring_thread(self):
        """Thread for scheduled monitoring"""
        while self.running:
            current_time = time.time()
            
            # Check for external trigger
            if self.check_trigger_file():
                print("External trigger detected")
                self.capture_and_analyze('triggered')
                
            # Scheduled capture
            elif current_time - self.last_capture > self.capture_interval:
                self.capture_and_analyze('scheduled')
                self.last_capture = current_time
                
            time.sleep(1)
            
    def cleanup_old_images(self):
        """Remove images older than 7 days"""
        try:
            cutoff_time = time.time() - (7 * 24 * 3600)
            
            for filename in os.listdir(IMAGE_DIR):
                filepath = os.path.join(IMAGE_DIR, filename)
                if os.path.getctime(filepath) < cutoff_time:
                    os.remove(filepath)
                    print(f"Cleaned old file: {filename}")
                    
        except Exception as e:
            print(f"Cleanup error: {e}")
            
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Crop Monitoring System - Component 198")
        print("=" * 60)
        
        # Connect camera
        if not self.connect_camera():
            print("❌ Cannot operate without camera")
            return
            
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitoring_thread)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print("\n✓ Crop monitoring operational")
        print(f"  • Capture interval: {self.capture_interval}s")
        print(f"  • Image directory: {IMAGE_DIR}")
        print(f"  • Trigger file: {TRIGGER_FILE}")
        print("  • Analyzing: Health, Maturity, Anomalies\n")
        
        # Initial capture
        self.capture_and_analyze('startup')
        
        # Main loop
        try:
            last_cleanup = time.time()
            
            while self.running:
                # Periodic cleanup (once per hour)
                if time.time() - last_cleanup > 3600:
                    self.cleanup_old_images()
                    last_cleanup = time.time()
                    
                # Status display
                print(f"\rTotal captures: {self.total_captures} | "
                      f"Latest health: {self.latest_analysis['health_score']:.0f}/100 | "
                      f"Stage: {self.latest_analysis['maturity_stage']:20s}", end='')
                      
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\nShutting down crop monitoring...")
            
        finally:
            self.running = False
            
            if self.pipeline:
                try:
                    self.pipeline.stop()
                except:
                    pass
                    
            print("✓ Crop monitoring stopped")

if __name__ == "__main__":
    system = CropMonitoringSystem()
    system.run()