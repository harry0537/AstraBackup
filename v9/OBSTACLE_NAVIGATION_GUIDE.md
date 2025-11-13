# Obstacle-Based Navigation Guide

## Overview

The `obstacle_navigation_v9.py` system enables the rover to drive autonomously using obstacle data **without requiring GPS waypoints**. It uses a reactive navigation approach that continuously reads proximity sensor data and steers toward open space.

## How It Works

### 1. Data Input
- Reads 8-sector proximity data from `/tmp/proximity_v9.json` (created by `combo_proximity_bridge_v9.py`)
- Each sector represents a 45° arc around the rover:
  - Sector 0: Front (0°)
  - Sector 1: Front-Right (45°)
  - Sector 2: Right (90°)
  - Sector 3: Rear-Right (135°)
  - Sector 4: Rear (180°)
  - Sector 5: Rear-Left (-135°)
  - Sector 6: Left (-90°)
  - Sector 7: Front-Left (-45°)

### 2. Navigation Algorithm

**Step 1: Find Best Direction**
- Scans all 8 sectors for the one with maximum clearance
- Prefers forward sectors (0, 1, 7) but will use sides/rear if forward is blocked

**Step 2: Calculate Steering**
- Converts target sector to steering angle
- Maps to PWM: 1500 ± 400 (center ± max deflection)
- Smooths steering when close to obstacles

**Step 3: Calculate Throttle**
- **Stop** if obstacle < 1.5m (SAFE_DISTANCE)
- **Slow** if obstacle < 3.0m (CAUTION_DISTANCE)
- **Normal** if obstacle > 3.0m

**Step 4: Send Commands**
- Sends RC override to Pixhawk via MAVLink
- Channel 1: Steering
- Channel 3: Throttle

## Usage

### Prerequisites

1. **Proximity Bridge Must Be Running**
   ```bash
   # Start proximity bridge first
   python3 combo_proximity_bridge_v9.py
   # OR use rover manager
   python3 rover_manager_v9.py
   ```

2. **Verify Proximity Data**
   ```bash
   # Check if proximity data exists
   cat /tmp/proximity_v9.json | python3 -m json.tool
   ```

### Starting Navigation

```bash
python3 obstacle_navigation_v9.py
```

### Expected Output

```
============================================================
Obstacle-Based Navigation V9
============================================================
[CONFIG] Pixhawk Port: /dev/ttyACM0
[CONFIG] Proximity File: /tmp/proximity_v9.json
============================================================

[Navigation Strategy]
  • Reads 8-sector proximity data from proximity bridge
  • Finds sector with most clearance
  • Steers toward that direction
  • Adjusts speed based on obstacle proximity
  • Stops if obstacles < 1.5m
  • No GPS waypoints - pure reactive navigation
============================================================

Connecting Pixhawk at /dev/ttyACM0...
✓ Pixhawk connected

Waiting for proximity data (max 30 seconds)...
✓ Proximity data available

[OK] Navigation system operational
  • Update rate: 10Hz
  • Safe distance: 1.5m
  • Caution distance: 3.0m
  • Press Ctrl+C to stop

[ 45s] MAV:✓ Prox:✓ Nav:ACTIVE | Min:2.3m | Steer:1500 Throttle:1600 | TX: 450 Stops:  0
```

## Configuration

### Navigation Parameters

Edit `obstacle_navigation_v9.py` to adjust:

```python
SAFE_DISTANCE_CM = 150      # Stop if obstacle < 1.5m
CAUTION_DISTANCE_CM = 300   # Slow down if obstacle < 3.0m
MAX_THROTTLE = 1600         # Maximum forward speed
MIN_THROTTLE = 1400         # Minimum forward speed
STEERING_RANGE = 400        # Max steering deflection (±400)
```

### Hardware Configuration

The system reads hardware config from `rover_config_v9.json`:

```json
{
  "proximity_bridge": {
    "pixhawk_port": "/dev/ttyACM0",
    "pixhawk_baud": 57600
  }
}
```

## Safety Features

1. **Automatic Stop on No Data**
   - Stops if proximity data unavailable
   - Stops if data is stale (> 2 seconds old)

2. **Obstacle Avoidance**
   - Hard stop if obstacle < 1.5m
   - Speed reduction if obstacle < 3.0m

3. **Graceful Shutdown**
   - Sends stop command on Ctrl+C
   - Waits for command to be sent

4. **Error Handling**
   - Continues operating if individual commands fail
   - Logs errors for debugging

## Troubleshooting

### "Cannot continue without Pixhawk"
- Check Pixhawk connection: `ls /dev/ttyACM*`
- Verify port in `rover_config_v9.json`
- Check permissions: `sudo usermod -a -G dialout $USER` (then logout/login)

### "Proximity bridge not detected"
- Start proximity bridge first: `python3 combo_proximity_bridge_v9.py`
- Check proximity file exists: `ls -lh /tmp/proximity_v9.json`
- Verify data is fresh: `cat /tmp/proximity_v9.json | grep timestamp`

### "Rover not moving"
- Check RC override is enabled in ArduPilot
- Verify channel mapping (Channel 1 = Steering, Channel 3 = Throttle)
- Check ArduPilot mode (should be MANUAL or GUIDED, not AUTO)
- Test with Mission Planner RC override first

### "Rover steering wrong direction"
- Check sector mapping matches ArduPilot orientation
- Verify LiDAR/camera mounting orientation
- Adjust sector-to-angle mapping in `calculate_steering()`

### "Rover stops too often"
- Increase `SAFE_DISTANCE_CM` (e.g., 200cm = 2.0m)
- Check if proximity sensors are too sensitive
- Verify obstacle data is accurate

### "Rover drives too fast"
- Reduce `MAX_THROTTLE` (e.g., 1550 instead of 1600)
- Reduce `MIN_THROTTLE` (e.g., 1450 instead of 1400)

## Advanced Usage

### Custom Navigation Strategies

You can modify the navigation algorithm in `navigate()`:

```python
def navigate(self):
    # Your custom logic here
    # Example: Always turn right
    steering = self.calculate_steering(1, sectors)  # Sector 1 = Front-Right
    throttle = self.calculate_throttle(sectors)
    self.send_rc_override(steering, throttle)
```

### Integration with Rover Manager

To add to rover manager, edit `rover_manager_v9.py`:

```python
COMPONENTS = [
    # ... existing components ...
    {
        'id': 199,
        'name': 'Obstacle Navigation',
        'script': 'obstacle_navigation_v9.py',
        'critical': False,
        'startup_delay': 5,
        'health_check': None
    }
]
```

## Performance

- **Update Rate**: 10Hz (100ms cycle)
- **Command Latency**: < 50ms
- **CPU Usage**: < 5% (on Raspberry Pi 4)
- **Memory**: < 50MB

## Limitations

1. **No Path Planning**: Pure reactive - doesn't plan ahead
2. **No Goal Seeking**: Doesn't navigate to specific locations
3. **No Memory**: Doesn't remember where it's been
4. **Local Minima**: May get stuck in corners (needs manual intervention)
5. **No GPS**: Doesn't use GPS for navigation

## Future Enhancements

Potential improvements:
- Path planning to avoid local minima
- Goal-seeking behavior (navigate toward GPS waypoint while avoiding obstacles)
- Memory/exploration map
- Speed optimization based on terrain
- Integration with row-following system

## See Also

- `combo_proximity_bridge_v9.py`: Provides obstacle data
- `v4/row_following_system.py`: Example of RC override usage
- ArduPilot Rover Documentation: RC override and obstacle avoidance

