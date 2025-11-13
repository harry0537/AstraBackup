# Fix: Rover Not Driving Around

## Current Status from Your Logs

✅ **Rover is ARMED** ("Throttle armed")
❌ **Mode issue** - "Flight mode change failed" / "No Mission. Can't set AUTO"
⚠️ **GPS Bad fix** - Expected for indoor testing

## The Problem

**You're trying to use AUTO mode, which requires GPS waypoints!**

For obstacle-based navigation without GPS, you **MUST use MANUAL mode**.

## Quick Fix

### Step 1: Set Mode to MANUAL

**In Mission Planner:**
1. Flight Data → Mode dropdown
2. Select **"MANUAL"** (NOT AUTO, NOT GUIDED)
3. Verify it shows "MANUAL" in status

**Why MANUAL?**
- AUTO = Requires GPS waypoints (won't work indoors)
- GUIDED = Requires GPS waypoints (won't work indoors)
- **MANUAL = Accepts RC override directly (works without GPS)**

### Step 2: Verify Navigation Script is Running

**Check Terminal:**
```bash
# Should see:
python3 obstacle_navigation_v9.py

# Output should show:
[OK] Navigation system operational
MAV:✓ Prox:✓ Nav:ACTIVE | Min:X.Xm | Steer:XXXX Throttle:XXXX
```

**If not running:**
```bash
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py
```

### Step 3: Check Navigation Script Output

**Watch for:**
- `Nav:ACTIVE` - Navigation is active
- `Throttle:1700` - Should be 1700 when clear (not 1500)
- `Steer:1500-1640` - Steering should change based on obstacles
- `TX:XXXX` - Commands being sent (number increasing)

**If throttle is stuck at 1500:**
- Obstacle too close - move to open area
- Or check proximity data: `cat /tmp/proximity_v9.json`

## Complete Checklist

Before expecting movement:

- [ ] **Mode = MANUAL** (not AUTO, not GUIDED)
- [ ] **Rover is ARMED** (you have this ✓)
- [ ] **Navigation script running** (`python3 obstacle_navigation_v9.py`)
- [ ] **Proximity bridge running** (provides sensor data)
- [ ] **Navigation shows `Nav:ACTIVE`**
- [ ] **Throttle value > 1500** (should be 1520-1700 when clear)
- [ ] **Steering values changing** (not stuck at 1500)
- [ ] **Commands being sent** (`TX:XXXX` increasing)

## Common Issues

### Issue 1: Mode is AUTO or GUIDED
**Symptom:** "No Mission. Can't set AUTO" or mode change fails
**Fix:** Set mode to **MANUAL**

### Issue 2: Navigation Script Not Running
**Symptom:** Rover armed but not moving
**Fix:** Start navigation script:
```bash
python3 obstacle_navigation_v9.py
```

### Issue 3: Throttle Stuck at 1500
**Symptom:** Commands sent but throttle always 1500 (stop)
**Fix:** 
- Check proximity data - obstacles might be too close
- Move rover to open area
- Or increase `SAFE_DISTANCE_CM` in script

### Issue 4: No Proximity Data
**Symptom:** Navigation script shows "Proximity data unavailable"
**Fix:** Start proximity bridge first:
```bash
python3 rover_manager_v9.py
# OR
python3 combo_proximity_bridge_v9.py
```

## Step-by-Step Test

### 1. Start Proximity Bridge
```bash
python3 rover_manager_v9.py
```
Wait for all components running.

### 2. Start Navigation Script
```bash
python3 obstacle_navigation_v9.py
```
Wait for: `Nav:ACTIVE`

### 3. Mission Planner Setup
- **Mode: MANUAL** (NOT AUTO!)
- **ARM the rover**
- **Watch navigation script output**

### 4. Expected Behavior

**When clear path:**
```
Steer:1500 Throttle:1700
→ Rover should move forward
```

**When obstacle detected:**
```
Steer:1640 Throttle:1600
→ Rover should steer right and slow down
```

**When obstacle too close:**
```
Steer:1500 Throttle:1500
→ Rover should stop
```

## Debug Commands

### Check if Navigation Script is Sending Commands
```bash
# Watch navigation script output
# Look for: Steer:XXXX Throttle:XXXX
# Values should change (not stuck)
```

### Check Proximity Data
```bash
cat /tmp/proximity_v9.json | python3 -m json.tool
```
Should show 8 sectors with distances.

### Test RC Override Manually
Mission Planner → Actions → Override RC Channels
- Set Channel 3 = 1700
- Does rover move? If yes, RC override works. If no, check hardware.

## Most Likely Issue

Based on your logs showing "No Mission. Can't set AUTO", you're probably trying to use **AUTO mode**.

**Solution:**
1. **Set mode to MANUAL** in Mission Planner
2. **ARM the rover** (you already have this)
3. **Start navigation script** if not running
4. **Watch for throttle values** - should be 1700 when clear

## Summary

**For obstacle navigation without GPS:**
- ✅ Mode: **MANUAL** (required!)
- ✅ Rover: **ARMED** (you have this)
- ✅ Navigation script: **Running** (check this)
- ✅ Proximity data: **Available** (check this)

**The rover will drive around obstacles automatically once:**
1. Mode is set to MANUAL
2. Navigation script is running
3. Proximity data is available
4. Path is clear (throttle > 1500)

