#!/usr/bin/env python3
"""
Project Astra NZ - Obstacle-Based Navigation V9
Drives rover using obstacle data without GPS waypoints
Component 199 - Reactive Navigation System
"""

import time
import threading
import json
import os
import sys
from pymavlink import mavutil

# Hardware configuration - Load from config file
def load_hardware_config():
    """Load hardware configuration from rover_config_v9.json"""
    config_file = "rover_config_v9.json"
    default_config = {
        'pixhawk_port': '/dev/ttyACM0',
        'pixhawk_baud': 57600
    }

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                prox_config = config.get('proximity_bridge', {})
                return {
                    'pixhawk_port': prox_config.get('pixhawk_port', default_config['pixhawk_port']),
                    'pixhawk_baud': prox_config.get('pixhawk_baud', default_config['pixhawk_baud'])
                }
        except Exception as e:
            print(f"[WARNING] Failed to load config: {e}, using defaults")

    return default_config

# Load hardware configuration
HARDWARE_CONFIG = load_hardware_config()
PIXHAWK_PORT = HARDWARE_CONFIG['pixhawk_port']
PIXHAWK_BAUD = HARDWARE_CONFIG['pixhawk_baud']
COMPONENT_ID = 199

# Proximity data file
PROXIMITY_FILE = '/tmp/proximity_v9.json'

# Navigation parameters
SAFE_DISTANCE_CM = 150  # Stop if obstacle closer than this (1.5m)
CAUTION_DISTANCE_CM = 300  # Slow down if obstacle closer than this (3m)
MAX_DISTANCE_CM = 2500  # Maximum sensor range
MIN_THROTTLE = 1520  # Minimum throttle (slow forward) - increased to overcome dead zone
MAX_THROTTLE = 1650  # Maximum throttle (moderate forward) - increased for better movement
STOP_THROTTLE = 1500  # Neutral/stop
STEERING_CENTER = 1500  # Center steering
STEERING_RANGE = 400  # Max steering deflection (±400 from center)


class ObstacleNavigation:
    """
    Obstacle-based navigation system that drives the rover using proximity data.
    
    Strategy:
    1. Read 8-sector proximity data from proximity bridge
    2. Find the sector with the most clearance (best direction)
    3. Steer toward that direction
    4. Adjust speed based on closest obstacle
    5. Stop if obstacles too close
    """
    
    def __init__(self):
        self.mavlink = None
        self.running = True
        
        # Current proximity data
        self.proximity_data = None
        self.proximity_lock = threading.Lock()
        self.last_proximity_update = 0
        
        # Navigation state
        self.current_steering = STEERING_CENTER
        self.current_throttle = STOP_THROTTLE
        self.navigation_active = False
        
        # Statistics
        self.stats = {
            'start_time': time.time(),
            'commands_sent': 0,
            'obstacle_stops': 0,
            'navigation_errors': 0,
            'last_error': None
        }
        
        # Sector mapping (8 sectors, 45° each)
        # Sector 0 = Front, 1 = Front-Right, 2 = Right, 3 = Rear-Right
        # Sector 4 = Rear, 5 = Rear-Left, 6 = Left, 7 = Front-Left
        # For navigation, we prefer forward sectors (0, 1, 7)
        self.forward_sectors = [0, 1, 7]
        self.right_sectors = [1, 2]
        self.left_sectors = [6, 7]
        
    def connect_pixhawk(self):
        """Connect to Pixhawk via MAVLink"""
        try:
            candidates = [PIXHAWK_PORT] + [f'/dev/ttyACM{i}' for i in range(4)]
            
            for port in candidates:
                if not os.path.exists(port):
                    continue
                try:
                    print(f"Connecting Pixhawk at {port}...")
                    self.mavlink = mavutil.mavlink_connection(
                        port,
                        baud=PIXHAWK_BAUD,
                        source_system=255,
                        source_component=COMPONENT_ID
                    )
                    self.mavlink.wait_heartbeat(timeout=5)
                    print("✓ Pixhawk connected")
                    return True
                except:
                    self.mavlink = None
                    continue
            
            raise RuntimeError('No Pixhawk port available')
            
        except Exception as e:
            print(f"✗ Pixhawk connection failed: {e}")
            return False
    
    def read_proximity_data(self):
        """Read latest proximity data from proximity bridge"""
        try:
            if not os.path.exists(PROXIMITY_FILE):
                return None
            
            with open(PROXIMITY_FILE, 'r') as f:
                data = json.load(f)
            
            # Check if data is fresh (< 2 seconds old)
            timestamp = data.get('timestamp', 0)
            age = time.time() - timestamp
            if age > 2.0:
                return None
            
            return data
            
        except Exception as e:
            self.stats['navigation_errors'] += 1
            self.stats['last_error'] = f"Read proximity: {e}"
            return None
    
    def find_best_direction(self, sectors):
        """
        Find the best direction to travel based on obstacle data.
        
        Returns:
            best_sector: Index of sector with most clearance
            clearance_cm: Distance to nearest obstacle in that sector
        """
        if not sectors or len(sectors) != 8:
            return None, 0
        
        # Prefer forward sectors, but consider all if forward is blocked
        best_sector = None
        best_clearance = 0
        
        # First, check forward sectors (preferred)
        for sector in self.forward_sectors:
            if sector < len(sectors):
                clearance = sectors[sector]
                if clearance > best_clearance:
                    best_clearance = clearance
                    best_sector = sector
        
        # If forward is blocked, check sides
        if best_clearance < SAFE_DISTANCE_CM:
            for sector in [2, 3, 4, 5, 6]:  # Right, Rear-Right, Rear, Rear-Left, Left
                if sector < len(sectors):
                    clearance = sectors[sector]
                    if clearance > best_clearance:
                        best_clearance = clearance
                        best_sector = sector
        
        return best_sector, best_clearance
    
    def calculate_steering(self, target_sector, sectors):
        """
        Calculate steering command to navigate toward target sector.
        
        Args:
            target_sector: Sector index (0-7) to steer toward
            sectors: Current sector distances
        
        Returns:
            steering_pwm: PWM value for steering (1000-2000)
        """
        if target_sector is None:
            return STEERING_CENTER
        
        # Convert sector to angle (0° = front, positive = right)
        # Sector 0 = 0°, 1 = 45°, 2 = 90°, 3 = 135°, 4 = 180°, 5 = -135°, 6 = -90°, 7 = -45°
        sector_angles = [0, 45, 90, 135, 180, -135, -90, -45]
        target_angle = sector_angles[target_sector] if target_sector < len(sector_angles) else 0
        
        # Normalize to -1.0 (left) to +1.0 (right)
        steering_normalized = target_angle / 90.0
        steering_normalized = max(-1.0, min(1.0, steering_normalized))
        
        # Convert to PWM (1500 ± 400)
        steering_pwm = int(STEERING_CENTER + steering_normalized * STEERING_RANGE)
        
        # Smooth steering if obstacles are close (avoid sharp turns near obstacles)
        if sectors and len(sectors) == 8:
            min_forward = min([sectors[i] for i in self.forward_sectors if i < len(sectors)])
            if min_forward < CAUTION_DISTANCE_CM:
                # Reduce steering intensity when close to obstacles
                steering_pwm = int(STEERING_CENTER + (steering_pwm - STEERING_CENTER) * 0.7)
        
        return steering_pwm
    
    def calculate_throttle(self, sectors):
        """
        Calculate throttle based on obstacle proximity.
        
        Args:
            sectors: Current sector distances
        
        Returns:
            throttle_pwm: PWM value for throttle (1000-2000)
        """
        if not sectors or len(sectors) != 8:
            return STOP_THROTTLE
        
        # Find minimum distance in forward sectors
        forward_distances = [sectors[i] for i in self.forward_sectors if i < len(sectors)]
        if not forward_distances:
            return STOP_THROTTLE
        
        min_forward = min(forward_distances)
        
        # Stop if obstacle too close
        if min_forward < SAFE_DISTANCE_CM:
            self.stats['obstacle_stops'] += 1
            return STOP_THROTTLE
        
        # Slow down if obstacle in caution zone
        if min_forward < CAUTION_DISTANCE_CM:
            # Linear interpolation: SAFE_DISTANCE -> MIN_THROTTLE, CAUTION_DISTANCE -> MAX_THROTTLE
            ratio = (min_forward - SAFE_DISTANCE_CM) / (CAUTION_DISTANCE_CM - SAFE_DISTANCE_CM)
            throttle = MIN_THROTTLE + ratio * (MAX_THROTTLE - MIN_THROTTLE)
            return int(throttle)
        
        # Full speed ahead if clear
        return MAX_THROTTLE
    
    def navigate(self):
        """Main navigation logic - called periodically"""
        if not self.mavlink:
            return
        
        # Read latest proximity data
        prox_data = self.read_proximity_data()
        if not prox_data:
            # No proximity data - stop
            if self.current_throttle != STOP_THROTTLE:
                self.send_rc_override(STEERING_CENTER, STOP_THROTTLE)
            return
        
        # Update proximity data
        with self.proximity_lock:
            self.proximity_data = prox_data
            self.last_proximity_update = time.time()
        
        # Get sector distances
        sectors = prox_data.get('sectors_cm', [])
        if not sectors or len(sectors) != 8:
            return
        
        # Find best direction
        best_sector, clearance = self.find_best_direction(sectors)
        
        # Calculate steering and throttle
        steering = self.calculate_steering(best_sector, sectors)
        throttle = self.calculate_throttle(sectors)
        
        # Send commands
        self.send_rc_override(steering, throttle)
        
        # Update state
        self.current_steering = steering
        self.current_throttle = throttle
        self.navigation_active = True
    
    def send_rc_override(self, steering_pwm, throttle_pwm):
        """Send RC override command to Pixhawk"""
        if not self.mavlink:
            return
        
        try:
            # Clamp PWM values to valid range
            steering_pwm = max(1000, min(2000, int(steering_pwm)))
            throttle_pwm = max(1000, min(2000, int(throttle_pwm)))
            
            # Send RC override
            # Channel 1 = Steering, Channel 3 = Throttle (typical ArduPilot rover setup)
            # Note: RC_OVERRIDE_TIME = 3 seconds, so we must send commands continuously
            self.mavlink.mav.rc_channels_override_send(
                self.mavlink.target_system,
                self.mavlink.target_component,
                steering_pwm,  # Channel 1 - Steering
                0,             # Channel 2
                throttle_pwm,  # Channel 3 - Throttle
                0,             # Channel 4
                0, 0, 0, 0,    # Channels 5-8
                0, 0, 0, 0, 0, 0, 0, 0,  # Channels 9-16
                0, 0           # Channels 17-18
            )
            
            # Flush to ensure message is sent immediately
            try:
                self.mavlink.flush()
            except:
                pass
            
            self.stats['commands_sent'] += 1
            
        except Exception as e:
            self.stats['navigation_errors'] += 1
            self.stats['last_error'] = f"RC override: {e}"
    
    def print_status(self):
        """Print navigation status"""
        uptime = int(time.time() - self.stats['start_time'])
        
        with self.proximity_lock:
            if self.proximity_data:
                sectors = self.proximity_data.get('sectors_cm', [])
                min_dist = min(sectors) if sectors else 0
                age = time.time() - self.last_proximity_update
            else:
                sectors = []
                min_dist = 0
                age = 999
        
        # Status indicators
        prox_status = "✓" if self.proximity_data and age < 2.0 else "✗"
        nav_status = "ACTIVE" if self.navigation_active else "STOPPED"
        mavlink_status = "✓" if self.mavlink else "✗"
        
        # Show sector data (abbreviated)
        sector_display = ""
        if sectors and len(sectors) == 8:
            sector_display = f" | Sectors: {' '.join(f'{int(s/100):2d}' for s in sectors[:4])}..."
        
        print(f"\r[{uptime:3d}s] "
              f"MAV:{mavlink_status} Prox:{prox_status} Nav:{nav_status} | "
              f"Min:{min_dist/100:.1f}m | "
              f"Steer:{self.current_steering} Throttle:{self.current_throttle} | "
              f"TX:{self.stats['commands_sent']:4d} Stops:{self.stats['obstacle_stops']:3d}"
              f"{sector_display}", end='', flush=True)
    
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Obstacle-Based Navigation V9")
        print("=" * 60)
        print(f"[CONFIG] Pixhawk Port: {PIXHAWK_PORT}")
        print(f"[CONFIG] Proximity File: {PROXIMITY_FILE}")
        print("=" * 60)
        print("\n[Navigation Strategy]")
        print("  • Reads 8-sector proximity data from proximity bridge")
        print("  • Finds sector with most clearance")
        print("  • Steers toward that direction")
        print("  • Adjusts speed based on obstacle proximity")
        print("  • Stops if obstacles < 1.5m")
        print("  • No GPS waypoints - pure reactive navigation")
        print("=" * 60)
        
        # Connect to Pixhawk
        pixhawk_ok = self.connect_pixhawk()
        if not pixhawk_ok:
            print("\n[ERROR] Cannot continue without Pixhawk")
            return
        
        # Wait for proximity data
        print("\nWaiting for proximity data (max 30 seconds)...")
        for i in range(30):
            if os.path.exists(PROXIMITY_FILE):
                data = self.read_proximity_data()
                if data:
                    print("✓ Proximity data available")
                    break
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"  Still waiting... ({i}/30 seconds)")
        
        if not os.path.exists(PROXIMITY_FILE):
            print("⚠ Proximity bridge not detected")
            print("  Start proximity bridge first:")
            print("    python3 combo_proximity_bridge_v9.py")
            print("  Or use rover manager:")
            print("    python3 rover_manager_v9.py")
            return
        
        print("\n[OK] Navigation system operational")
        print("  • Update rate: 10Hz")
        print("  • Safe distance: 1.5m")
        print("  • Caution distance: 3.0m")
        print("  • Press Ctrl+C to stop\n")
        
        try:
            last_nav = time.time()
            last_status = time.time()
            last_heartbeat = time.time()
            
            while self.running:
                # Navigate at 10Hz (must be faster than RC_OVERRIDE_TIME=3s)
                if time.time() - last_nav > 0.1:
                    self.navigate()
                    last_nav = time.time()
                
                # Send heartbeat to maintain connection (every 1 second)
                if time.time() - last_heartbeat > 1.0:
                    try:
                        if self.mavlink:
                            self.mavlink.mav.heartbeat_send(
                                type=0,  # MAV_TYPE_GENERIC
                                autopilot=0,  # MAV_AUTOPILOT_INVALID
                                base_mode=0,
                                custom_mode=0,
                                system_status=3  # MAV_STATE_STANDBY
                            )
                    except:
                        pass
                    last_heartbeat = time.time()
                
                # Print status at 1Hz
                if time.time() - last_status > 1.0:
                    self.print_status()
                    last_status = time.time()
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Stopping navigation...")
        
        finally:
            self.running = False
            
            # Send stop command
            if self.mavlink:
                try:
                    self.send_rc_override(STEERING_CENTER, STOP_THROTTLE)
                    time.sleep(0.5)
                except:
                    pass
            
            print("[OK] Navigation stopped")
            print(f"  • Commands sent: {self.stats['commands_sent']}")
            print(f"  • Obstacle stops: {self.stats['obstacle_stops']}")
            print(f"  • Errors: {self.stats['navigation_errors']}")


if __name__ == "__main__":
    nav = ObstacleNavigation()
    nav.run()

