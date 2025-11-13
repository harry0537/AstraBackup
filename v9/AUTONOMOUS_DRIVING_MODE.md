# Autonomous Driving Mode - Indoor Testing

## Overview

The obstacle navigation system enables **autonomous driving** for indoor testing:
- **Accelerates forward** when path is clear
- **Uses proximity data** to navigate around obstacles
- **Avoids obstacles** by steering toward open space
- **No GPS required** - perfect for indoor testing

## How It Works

### 1. Forward Movement (Acceleration)

**When path is clear (> 3m):**
- Throttle: `1700` (maximum forward speed)
- Steering: `1500` (straight ahead)
- **Rover accelerates forward**

**When obstacle detected (1.5m - 3m):**
- Throttle: `1520-1700` (slows down based on distance)
- Steering: Adjusts toward open space
- **Rover slows down but continues**

**When obstacle too close (< 1.5m):**
- Throttle: `1500` (stop)
- Steering: `1500` (straight)
- **Rover stops**

### 2. Obstacle Avoidance (Steering)

**Navigation algorithm:**
1. Scans 8 sectors around rover (45° each)
2. Finds sector with most clearance
3. Steers toward that direction
4. Prefers forward sectors when clear
5. Uses sides/rear if forward blocked

**Steering behavior:**
- `Steer:1500` = Straight ahead
- `Steer:1640` = Turn right
- `Steer:1360` = Turn left
- Adjusts smoothly based on obstacle position

### 3. Proximity-Based Navigation

**8-Sector Detection:**
- Sector 0: Front
- Sector 1: Front-Right
- Sector 2: Right
- Sector 3: Rear-Right
- Sector 4: Rear
- Sector 5: Rear-Left
- Sector 6: Left
- Sector 7: Front-Left

**Decision Making:**
- If forward clear (> 2m): Go straight forward
- If forward blocked: Find best escape route
- Always prefer forward when possible
- Steer around obstacles smoothly

## Setup for Autonomous Driving

### Step 1: Start Components

**Terminal 1:**
```bash
python3 rover_manager_v9.py
```

**Terminal 2:**
```bash
python3 obstacle_navigation_v9.py
```

### Step 2: Configure Mission Planner

1. **Set Mode to MANUAL** (not GUIDED)
2. **ARM the rover**
3. **Verify proximity sensors** showing 8 sectors

### Step 3: Watch Navigation

**Navigation script output shows:**
```
[ 45s] MAV:✓ Prox:✓ Nav:ACTIVE | Min:2.3m | Steer:1500 Throttle:1700 | TX: 450 Stops:  0
```

**What to watch:**
- `Throttle:1700` = Accelerating forward (clear path)
- `Throttle:1520-1699` = Slowing down (obstacle detected)
- `Throttle:1500` = Stopped (obstacle too close)
- `Steer:1500` = Going straight
- `Steer:1640` = Turning right (avoiding obstacle)
- `Steer:1360` = Turning left (avoiding obstacle)

## Expected Behavior

### Scenario 1: Clear Path
```
Proximity: All sectors > 3m
→ Throttle: 1700 (accelerate)
→ Steering: 1500 (straight)
→ Result: Rover drives forward
```

### Scenario 2: Obstacle Ahead
```
Proximity: Front sector < 3m
→ Throttle: 1600 (slow down)
→ Steering: 1640 (turn right toward open space)
→ Result: Rover steers around obstacle
```

### Scenario 3: Obstacle Too Close
```
Proximity: Front sector < 1.5m
→ Throttle: 1500 (stop)
→ Steering: 1500 (straight)
→ Result: Rover stops to avoid collision
```

### Scenario 4: Forward Blocked
```
Proximity: All forward sectors < 1.5m
→ Throttle: 1500 (stop)
→ Steering: 1640 or 1360 (turn toward best escape)
→ Result: Rover turns to find open path
```

## Tuning Parameters

### Increase Speed
Edit `obstacle_navigation_v9.py`:
```python
MAX_THROTTLE = 1750  # Increase from 1700 for faster speed
```

### Increase Safety Distance
```python
SAFE_DISTANCE_CM = 200  # Stop at 2m instead of 1.5m
CAUTION_DISTANCE_CM = 400  # Slow down at 4m instead of 3m
```

### More Aggressive Steering
```python
STEERING_RANGE = 500  # Increase from 400 for sharper turns
```

## Troubleshooting

### Rover Not Accelerating

**Check:**
1. Mode is **MANUAL** (not GUIDED)
2. Rover is **ARMED**
3. Proximity data shows clear path (> 3m)
4. Throttle value in output is `1700` (not `1500`)

**If throttle is 1500:**
- Obstacle too close - move to open area
- Or increase `SAFE_DISTANCE_CM`

### Rover Not Steering Around Obstacles

**Check:**
1. Proximity sensors detecting obstacles (sectors < 2500cm)
2. Steering values changing in output
3. Best direction calculation working

**Debug:**
- Watch sector values in proximity data
- Check which sector has most clearance
- Verify steering commands being sent

### Rover Stops Too Often

**Fix:**
- Increase `SAFE_DISTANCE_CM` (e.g., 200cm = 2m)
- Check if proximity sensors too sensitive
- Verify obstacle data is accurate

## Safety Features

1. **Automatic Stop** if obstacle < 1.5m
2. **Speed Reduction** if obstacle < 3m
3. **Stop on No Data** if proximity data unavailable
4. **Stop on Shutdown** sends stop command

## Summary

**For autonomous indoor driving:**
- ✅ Accelerates forward when clear
- ✅ Uses proximity data for navigation
- ✅ Steers around obstacles
- ✅ Stops when too close
- ✅ No GPS required

**The rover will:**
1. Start moving forward
2. Detect obstacles with proximity sensors
3. Steer toward open space
4. Slow down near obstacles
5. Stop if too close
6. Continue exploring when clear

**Perfect for indoor autonomous testing!**

