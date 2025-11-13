# Autonomous Steering - How It Works

## Overview

The rover now uses **autonomous steering** that automatically drives around obstacles using all sensor data. It uses a **potential field method** that combines:
- **Repulsion from obstacles** (pushes rover away)
- **Attraction to open space** (pulls rover toward clear areas)

## How It Works

### 1. Potential Field Method

**Repulsion (from obstacles):**
- Each detected obstacle creates a repulsion force
- Closer obstacles = stronger repulsion
- Direction: away from obstacle (180° from obstacle direction)

**Attraction (to open space):**
- Open areas create attraction force
- Clearer areas = stronger attraction
- Direction: toward open space (especially forward)

**Combined Result:**
- Repulsion + Attraction = Steering direction
- Rover automatically steers around obstacles toward open space

### 2. Using All 8 Sectors

**The algorithm processes all 8 sectors:**
- Sector 0: Front
- Sector 1: Front-Right
- Sector 2: Right
- Sector 3: Rear-Right
- Sector 4: Rear
- Sector 5: Rear-Left
- Sector 6: Left
- Sector 7: Front-Left

**For each sector:**
- If obstacle detected: Calculate repulsion force
- If clear space: Calculate attraction force
- Sum all forces to get steering direction

### 3. Steering Calculation

**Step 1: Calculate Repulsion**
```
For each sector with obstacle:
  repulsion_strength = f(distance)  // Stronger when closer
  repulsion_vector = repulsion_strength * direction_away_from_obstacle
```

**Step 2: Calculate Attraction**
```
For each sector with clear space:
  attraction_strength = f(clearance)  // Stronger when clearer
  attraction_vector = attraction_strength * direction_toward_open_space
  (3x stronger for forward sectors)
```

**Step 3: Combine Vectors**
```
total_vector = sum(repulsion_vectors) + sum(attraction_vectors)
steering_angle = atan2(total_vector.y, total_vector.x)
```

**Step 4: Convert to Steering Command**
```
steering_pwm = 1500 + (steering_angle / 90°) * 400
```

### 4. Smooth Steering

**Low-pass filter applied:**
- Blends 70% new steering + 30% previous steering
- Prevents oscillations and jerky movements
- Provides smooth, continuous steering

## Behavior Examples

### Example 1: Obstacle on Right Side
```
Sensors detect:
  Front: Clear (5m)
  Front-Right: Clear (4m)
  Right: Obstacle (1m)  ← Close obstacle
  Left: Clear (6m)

Repulsion:
  Right obstacle pushes rover LEFT (strong)

Attraction:
  Front/Left clear areas pull rover FORWARD/LEFT

Result:
  Rover steers LEFT to avoid obstacle, continues forward
```

### Example 2: Obstacle Straight Ahead
```
Sensors detect:
  Front: Obstacle (2m)  ← Blocking path
  Front-Right: Clear (4m)
  Front-Left: Clear (3m)
  Right: Clear (5m)
  Left: Clear (5m)

Repulsion:
  Front obstacle pushes rover BACK (strong)

Attraction:
  Right/Left clear areas pull rover RIGHT/LEFT

Result:
  Rover steers RIGHT or LEFT (whichever is clearer) to go around
```

### Example 3: Clear Path Ahead
```
Sensors detect:
  All forward sectors: Clear (> 3m)
  All side sectors: Clear (> 3m)

Repulsion:
  None (no close obstacles)

Attraction:
  Strong forward attraction (forward bias)

Result:
  Rover steers straight forward (steering = 1500)
```

## Key Features

### 1. Autonomous Navigation
- **No manual steering required**
- Rover automatically steers based on sensor data
- Continuously adapts to environment

### 2. Obstacle Avoidance
- **Repulsion from obstacles** - automatically steers away
- **Attraction to open space** - moves toward clear areas
- **Smooth steering** - no jerky movements

### 3. Forward Preference
- **50% forward bias** - prefers going forward
- **3x stronger attraction** for forward sectors
- **Avoids backing up** unless necessary

### 4. Responsive Steering
- **Uses all 8 sectors** - comprehensive obstacle detection
- **Distance-based repulsion** - closer obstacles = stronger avoidance
- **Clearance-based attraction** - clearer areas = stronger attraction

## Tuning Parameters

### Increase Steering Aggressiveness
Edit `obstacle_navigation_v9.py`:
```python
# In calculate_steering():
repulsion_strength = 30.0 / max(distance_m, 0.1)  # Increase from 20.0
```

### Increase Forward Bias
```python
forward_bias = 0.7  # Increase from 0.5 (70% forward preference)
```

### More Aggressive Steering
```python
STEERING_RANGE = 500  # Increase from 400 (sharper turns)
```

### Smoother Steering
```python
# In calculate_steering():
steering_pwm = int(steering_pwm * 0.5 + self.previous_steering * 0.5)  # More smoothing
```

## Expected Behavior

### When Clear Path:
- Steering: `1500` (straight)
- Throttle: `1700` (forward)
- Result: **Drives straight forward**

### When Obstacle Detected:
- Steering: `1360-1640` (turns left/right)
- Throttle: `1520-1700` (slows down)
- Result: **Steers around obstacle while moving forward**

### When Obstacle Too Close:
- Steering: `1360-1640` (turns away)
- Throttle: `1500` (stops)
- Result: **Stops and turns to find open path**

## Summary

**The rover now:**
1. ✅ **Automatically steers** using all sensor data
2. ✅ **Drives around obstacles** using potential field method
3. ✅ **Prefers forward movement** but steers when needed
4. ✅ **Smooth steering** - no oscillations
5. ✅ **Continuous navigation** - adapts in real-time

**No manual intervention needed** - the rover autonomously navigates using sensor data!

