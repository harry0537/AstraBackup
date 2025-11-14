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
import math
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
MAX_THROTTLE = 1700  # Maximum throttle (good forward speed) - increased for acceleration
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
        self.previous_steering = STEERING_CENTER  # For smoothing
        
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
        Prioritizes forward movement but steers around obstacles.
        
        Returns:
            best_sector: Index of sector with most clearance
            clearance_cm: Distance to nearest obstacle in that sector
        """
        if not sectors or len(sectors) != 8:
            return None, 0
        
        # Prefer forward sectors for normal driving
        best_sector = None
        best_clearance = 0
        
        # Check forward sectors first (preferred for forward movement)
        forward_clearance = 0
        for sector in self.forward_sectors:
            if sector < len(sectors):
                clearance = sectors[sector]
                forward_clearance = max(forward_clearance, clearance)
                if clearance > best_clearance:
                    best_clearance = clearance
                    best_sector = sector
        
        # If forward is clear enough (> 2m), prefer forward
        if forward_clearance > 200:
            # Find best forward sector
            for sector in self.forward_sectors:
                if sector < len(sectors) and sectors[sector] > 200:
                    return sector, sectors[sector]
        
        # If forward is blocked (< 1.5m), find best escape direction
        if forward_clearance < SAFE_DISTANCE_CM:
            # Check all sectors for best escape route
            for sector in range(8):
                if sector < len(sectors):
                    clearance = sectors[sector]
                    if clearance > best_clearance:
                        best_clearance = clearance
                        best_sector = sector
        
        # If no good direction found, use forward anyway (will slow down)
        if best_sector is None:
            best_sector = 0  # Default to forward
            best_clearance = sectors[0] if sectors else 0
        
        return best_sector, best_clearance
    
    def calculate_steering(self, target_sector, sectors):
        """
        Calculate autonomous steering using all sensor data.
        Uses potential field method: repulsion from obstacles + attraction to open space.
        This makes the rover automatically steer around obstacles.
        
        Args:
            target_sector: Sector index (0-7) - hint for preferred direction
            sectors: Current sector distances (8 values) - all sensor data
        
        Returns:
            steering_pwm: PWM value for steering (1000-2000)
        """
        if not sectors or len(sectors) != 8:
            return STEERING_CENTER
        
        # Sector angles in degrees (0° = front, positive = right, negative = left)
        # Sector 0 = 0° (front), 1 = 45° (front-right), 2 = 90° (right), 3 = 135° (rear-right)
        # Sector 4 = 180° (rear), 5 = -135° (rear-left), 6 = -90° (left), 7 = -45° (front-left)
        sector_angles_deg = [0, 45, 90, 135, 180, -135, -90, -45]
        
        # Calculate steering using potential field method
        # Repulsion: obstacles push rover away (stronger when closer)
        # Attraction: open space pulls rover forward (stronger when clearer)
        
        # Forward bias - prefer going forward
        forward_bias = 0.5  # 50% bias toward forward movement
        
        # Calculate repulsion vector from obstacles
        repulsion_x = 0.0
        repulsion_y = 0.0
        
        for i, distance_cm in enumerate(sectors):
            if distance_cm >= MAX_DISTANCE_CM:
                continue  # No obstacle detected, skip
            
            # Calculate repulsion strength (inverse of distance)
            # Closer obstacles = stronger repulsion
            distance_m = distance_cm / 100.0  # Convert to meters
            
            if distance_m < (SAFE_DISTANCE_CM / 100.0):
                # Very close - very strong repulsion
                repulsion_strength = 20.0 / max(distance_m, 0.1)
            elif distance_m < (CAUTION_DISTANCE_CM / 100.0):
                # Close - strong repulsion
                repulsion_strength = 10.0 / max(distance_m, 0.3)
            else:
                # Far - weak repulsion
                repulsion_strength = 2.0 / max(distance_m, 1.0)
            
            # Convert sector angle to radians
            angle_rad = math.radians(sector_angles_deg[i])
            
            # Calculate repulsion vector (away from obstacle)
            # Obstacle at angle θ pushes rover away in direction (θ + 180°)
            repulsion_x += repulsion_strength * math.cos(angle_rad + math.pi)
            repulsion_y += repulsion_strength * math.sin(angle_rad + math.pi)
        
        # Calculate attraction vector toward open space (forward preference)
        attraction_x = forward_bias  # Forward bias
        attraction_y = 0.0
        
        # Add attraction to sectors with most clearance (especially forward)
        max_clearance = max(sectors)
        if max_clearance > 200:  # If any sector is clear (> 2m)
            for i, distance_cm in enumerate(sectors):
                if distance_cm > 200:
                    # Calculate attraction strength based on clearance
                    clearance_m = distance_cm / 100.0
                    attraction_strength = (clearance_m - 2.0) / 5.0  # Stronger for more clearance
                    
                    angle_rad = math.radians(sector_angles_deg[i])
                    
                    # Attraction toward open space (especially forward sectors)
                    if i in self.forward_sectors:
                        attraction_x += attraction_strength * math.cos(angle_rad) * 3.0  # 3x for forward
                        attraction_y += attraction_strength * math.sin(angle_rad) * 3.0
                    else:
                        attraction_x += attraction_strength * math.cos(angle_rad) * 0.3  # Less for sides
                        attraction_y += attraction_strength * math.sin(angle_rad) * 0.3
        
        # Combine repulsion and attraction
        total_x = repulsion_x + attraction_x
        total_y = repulsion_y + attraction_y
        
        # Calculate desired steering angle from combined vector
        if abs(total_x) < 0.001 and abs(total_y) < 0.001:
            # No clear direction - go straight forward
            steering_angle_deg = 0.0
        else:
            steering_angle_deg = math.degrees(math.atan2(total_y, total_x))
        
        # Normalize steering angle to -90° to +90° range (rover can't turn more than 90°)
        steering_angle_deg = max(-90.0, min(90.0, steering_angle_deg))
        
        # Convert to normalized steering (-1.0 = full left, +1.0 = full right)
        steering_normalized = steering_angle_deg / 90.0
        
        # Convert to PWM (1500 ± 400)
        steering_pwm = int(STEERING_CENTER + steering_normalized * STEERING_RANGE)
        
        # Smooth steering to avoid oscillations (low-pass filter)
        if hasattr(self, 'previous_steering'):
            # Smooth by blending 70% new + 30% previous value
            steering_pwm = int(steering_pwm * 0.7 + self.previous_steering * 0.3)
        else:
            self.previous_steering = STEERING_CENTER
        
        self.previous_steering = steering_pwm
        
        return steering_pwm
    
    def calculate_throttle(self, sectors):
        """
        Calculate throttle based on obstacle proximity.
        Accelerates when clear, slows down near obstacles.
        
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
        
        # Stop if obstacle too close (< 1.5m)
        if min_forward < SAFE_DISTANCE_CM:
            self.stats['obstacle_stops'] += 1
            return STOP_THROTTLE
        
        # Slow down if obstacle in caution zone (1.5m - 3m)
        if min_forward < CAUTION_DISTANCE_CM:
            # Linear interpolation: SAFE_DISTANCE -> MIN_THROTTLE, CAUTION_DISTANCE -> MAX_THROTTLE
            ratio = (min_forward - SAFE_DISTANCE_CM) / (CAUTION_DISTANCE_CM - SAFE_DISTANCE_CM)
            throttle = MIN_THROTTLE + ratio * (MAX_THROTTLE - MIN_THROTTLE)
            return int(throttle)
        
        # Full speed ahead if clear (> 3m) - accelerate!
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
        
        # Find best direction (hint for steering algorithm)
        best_sector, clearance = self.find_best_direction(sectors)
        
        # Calculate autonomous steering using all sensor data
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
            # Channel 1 = Steering (Yaw), Channel 2 = Throttle (based on rover_baseline_v9.param)
            # RCMAP_YAW = 1, RCMAP_THROTTLE = 2
            # Note: RC_OVERRIDE_TIME = 3 seconds, so we must send commands continuously
            self.mavlink.mav.rc_channels_override_send(
                self.mavlink.target_system,
                self.mavlink.target_component,
                steering_pwm,  # Channel 1 - Steering (Yaw)
                throttle_pwm,  # Channel 2 - Throttle (FIXED: was Channel 3)
                0,             # Channel 3
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
        print("  • Autonomous steering using potential field method")
        print("  • Repulsion from obstacles + Attraction to open space")
        print("  • Steers automatically based on all sensor data")
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
        print("  • Safe distance: 1.5m (stops if closer)")
        print("  • Caution distance: 3.0m (slows down)")
        print("  • Max throttle: 1700 (good forward speed)")
        print("  • Press Ctrl+C to stop\n")
        print("⚠️  IMPORTANT: Set rover to MANUAL mode (not GUIDED)")
        print("   GUIDED mode requires GPS waypoints - use MANUAL for RC override")
        print("   Rover will accelerate forward when clear, steer around obstacles\n")
        
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

