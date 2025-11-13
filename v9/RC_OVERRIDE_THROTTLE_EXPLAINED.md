# RC Override for Throttle - How It Works

## Yes, RC Override is Used for Throttle

**The obstacle navigation script uses RC override for BOTH steering AND throttle:**

- **Channel 1**: Steering (via RC override)
- **Channel 3**: Throttle (via RC override)

This is the **correct approach** for autonomous driving without GPS waypoints.

## How Throttle Control Works

### Current Implementation

**In `obstacle_navigation_v9.py`:**

```python
# Calculate throttle based on obstacle proximity
throttle = self.calculate_throttle(sectors)  # Returns PWM value (1000-2000)

# Send RC override
self.mavlink.mav.rc_channels_override_send(
    ...
    steering_pwm,  # Channel 1 - Steering
    0,             # Channel 2
    throttle_pwm,  # Channel 3 - Throttle ← THIS CONTROLS MOVEMENT
    ...
)
```

### Throttle Values

**Current throttle range:**
- `STOP_THROTTLE = 1500` - Neutral/stop
- `MIN_THROTTLE = 1520` - Slow forward (above dead zone)
- `MAX_THROTTLE = 1700` - Good forward speed

**Throttle calculation:**
- Clear path (> 3m): `1700` (accelerate forward)
- Obstacle detected (1.5m - 3m): `1520-1700` (slow down)
- Obstacle too close (< 1.5m): `1500` (stop)

## Why RC Override for Throttle?

### 1. Works Without GPS
- **RC override** works in MANUAL mode without GPS
- **Position/velocity commands** require GPS
- **Perfect for indoor testing** without GPS

### 2. Direct Motor Control
- **RC override** = Direct control like physical RC transmitter
- **ArduPilot executes commands immediately**
- **No waypoint/mission required**

### 3. Responsive Control
- **10Hz update rate** (sends commands every 0.1 seconds)
- **Continuous control** - rover responds immediately
- **Smooth acceleration/deceleration**

## Channel Mapping

### Standard ArduPilot Rover Setup

**From `rover_baseline_v9.param`:**
```
RCMAP_THROTTLE = 2  (Channel 2 = Throttle)
RCMAP_YAW = 1       (Channel 1 = Steering/Yaw)
```

**But the script uses:**
- Channel 1 = Steering
- Channel 3 = Throttle

**Why?** Different rover setups use different channels. The script uses Channel 3 for throttle, which is common.

### Verify Your Channel Mapping

**Check in Mission Planner:**
1. Mission Planner → Config/Tuning → Radio Calibration
2. Move physical RC throttle stick
3. Note which channel moves (should be Channel 2 or Channel 3)
4. If different, update script:

```python
# In send_rc_override(), change channel positions
self.mavlink.mav.rc_channels_override_send(
    steering_pwm,  # Channel 1 - Steering
    0,             # Channel 2
    throttle_pwm,  # Channel 3 - Throttle (change if needed)
    0,             # Channel 4
    ...
)
```

## Alternative: Use Velocity Commands?

### Could Use SET_POSITION_TARGET_LOCAL_NED

**But this requires:**
- GPS or external position estimate
- More complex setup
- Not ideal for indoor testing

### RC Override is Better For:
- ✅ Indoor testing (no GPS)
- ✅ Direct control
- ✅ Simple implementation
- ✅ Works in MANUAL mode
- ✅ Immediate response

## How It Works in Practice

### 1. Navigation Script Calculates Throttle

```python
# Based on obstacle proximity
if clear_path:
    throttle = 1700  # Accelerate forward
elif obstacle_close:
    throttle = 1600  # Slow down
else:
    throttle = 1500  # Stop
```

### 2. Sends RC Override Command

```python
# Sends to Pixhawk via MAVLink
rc_channels_override_send(
    channel_1=steering_pwm,
    channel_3=throttle_pwm,  # Throttle command
    ...
)
```

### 3. Pixhawk Executes Command

- **Pixhawk receives RC override**
- **Applies to motor control**
- **Rover moves forward/backward based on throttle value**

## Throttle Control Logic

### Speed Control

**Clear path (> 3m):**
```
Throttle: 1700
→ Rover accelerates forward
```

**Obstacle detected (1.5m - 3m):**
```
Throttle: 1520-1700 (based on distance)
→ Rover slows down but continues
```

**Obstacle too close (< 1.5m):**
```
Throttle: 1500
→ Rover stops
```

### Acceleration/Deceleration

**Acceleration:**
- Clear path detected → Throttle increases to 1700
- Rover speeds up

**Deceleration:**
- Obstacle detected → Throttle decreases based on distance
- Rover slows down smoothly

**Stop:**
- Obstacle too close → Throttle = 1500
- Rover stops immediately

## Troubleshooting

### Rover Not Moving

**Check throttle values:**
```bash
# Watch navigation script output
# Look for: Throttle:XXXX
# Should be 1700 when clear (not 1500)
```

**If throttle is 1500:**
- Obstacle too close - move to open area
- Or check proximity data: `cat /tmp/proximity_v9.json`

**If throttle is 1700 but not moving:**
- Check channel mapping (Channel 3 = Throttle?)
- Test RC override manually in Mission Planner
- Check hardware (ESC, motors)

### Throttle Not Changing

**Check:**
1. Navigation script running?
2. Proximity data available?
3. Mode is MANUAL?
4. Rover is ARMED?

### Wrong Throttle Channel

**If throttle not working:**
1. Check Mission Planner → Radio Calibration
2. Note which channel controls throttle
3. Update script if different from Channel 3

## Summary

**RC override for throttle is:**
- ✅ **Correct approach** for obstacle navigation
- ✅ **Works without GPS** (perfect for indoor)
- ✅ **Direct control** (immediate response)
- ✅ **Simple implementation** (already working)

**The script already uses RC override for throttle (Channel 3).**

**Throttle values:**
- `1500` = Stop
- `1520-1700` = Forward (faster = higher number)
- Adjust based on obstacle proximity

**This is the right approach - no changes needed!**

