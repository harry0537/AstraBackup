# Troubleshooting: Rover Not Moving with Obstacle Navigation

## Common Issues and Fixes

### Issue 1: RC Override Timeout

**Problem:** `RC_OVERRIDE_TIME = 3` seconds - commands must be sent continuously

**Fix:**
- Navigation script sends at 10Hz (every 0.1s) - this is fine
- But verify commands are actually being sent
- Check navigation script output shows `TX:XXXX` increasing

**Verify:**
```bash
# Watch navigation script output
# Should see: TX: 450, 460, 470... (increasing)
```

---

### Issue 2: Throttle Values Too Low

**Problem:** Throttle 1400-1600 might not overcome dead zone

**Fix Applied:**
- Changed `MIN_THROTTLE = 1520` (was 1400)
- Changed `MAX_THROTTLE = 1650` (was 1600)
- This should provide better movement

**Test:**
- Watch navigation script output
- When clear path: `Throttle:1650` (should move forward)
- When obstacle close: `Throttle:1500` (stops)

---

### Issue 3: Wrong Channel Mapping

**Problem:** Steering/Throttle on wrong channels

**Current Setup:**
- Channel 1 = Steering
- Channel 3 = Throttle

**Verify in Mission Planner:**
1. Mission Planner → Config/Tuning → Radio Calibration
2. Move physical RC stick for steering - note which channel moves
3. Move physical RC stick for throttle - note which channel moves
4. If different, update `obstacle_navigation_v9.py`:
   ```python
   # In send_rc_override(), change channel positions
   self.mavlink.mav.rc_channels_override_send(
       ...
       steering_pwm,  # Change this channel number
       ...
       throttle_pwm,  # Change this channel number
       ...
   )
   ```

---

### Issue 4: RC Override Not Enabled

**Problem:** ArduPilot not accepting RC override

**Fix:**
- Mission Planner → Config/Tuning → Full Parameter List
- Check `RC_OVERRIDE_TIME` - should be `3` (not `0`)
- If `0`, set to `3` and reboot

**Verify:**
- Mission Planner → Flight Data → Actions → "Override RC Channels"
- Try manually setting Channel 1 and Channel 3
- If rover responds, RC override is working

---

### Issue 5: Safety Checks Blocking Movement

**Problem:** Safety parameters preventing movement

**Check:**
- Mission Planner → Config/Tuning → Safety
- `ARMING_CHECK` - should be `1` or `0` (not blocking)
- `ARMING_RUDDER` - should be `2` (allows arming without GPS)

**Also Check:**
- `ATC_BRAKE` - should be `0` (brake disabled)
- `ATC_STOP_SPEED` - should be low (e.g., `0.1`)

---

### Issue 6: Mode Not Accepting RC Override

**Problem:** Wrong flight mode

**Required Mode:**
- **GUIDED** - Best (allows RC override + safety features)
- **MANUAL** - Also works (direct control)

**NOT:**
- **AUTO** - Tries to follow waypoints (conflicts with RC override)
- **HOLD** - Holds position (won't move)

**Verify:**
- Mission Planner → Flight Data → Mode
- Should show "GUIDED" or "MANUAL"

---

### Issue 7: Rover Not Armed

**Problem:** Rover must be ARMED to move

**Fix:**
- Mission Planner → Flight Data → Actions → "ARM"
- Verify status shows "ARMED"

**If won't arm:**
- Check `ARMING_CHECK` parameter
- Check for pre-arm failures in Mission Planner messages
- Disable GPS requirement: `ARMING_CHECK = 1`, `ARMING_RUDDER = 2`

---

### Issue 8: Throttle Dead Zone

**Problem:** Throttle needs to be above dead zone to move

**Typical Dead Zones:**
- Center: 1500
- Dead zone: ±20-50 (1480-1520)
- Need: 1520+ for forward movement

**Fix Applied:**
- `MIN_THROTTLE = 1520` (above dead zone)
- `MAX_THROTTLE = 1650` (good forward speed)

**If still not moving, try:**
- Increase `MAX_THROTTLE` to `1700` or `1750`
- Test manually in Mission Planner first

---

## Diagnostic Steps

### Step 1: Verify Commands Being Sent
```bash
# Watch navigation script output
# Look for: Steer:XXXX Throttle:XXXX
# Values should change (not stuck at 1500)
```

### Step 2: Test RC Override Manually
1. Mission Planner → Flight Data → Actions
2. "Override RC Channels"
3. Set Channel 1 = 1600 (steer right)
4. Set Channel 3 = 1600 (throttle forward)
5. Does rover move? If yes, RC override works. If no, check channel mapping.

### Step 3: Check Mission Planner Messages
- Look for "RC override" messages
- Look for errors or warnings
- Check if commands are being rejected

### Step 4: Verify Proximity Data
```bash
# Check proximity data
cat /tmp/proximity_v9.json | python3 -m json.tool

# Should show sectors with distances
# If all 2500cm, no obstacles detected (rover should move forward)
```

### Step 5: Test with Higher Throttle
Edit `obstacle_navigation_v9.py`:
```python
MAX_THROTTLE = 1700  # Increase from 1650
```

---

## Quick Fixes to Try

### Fix 1: Increase Throttle Range
```python
# In obstacle_navigation_v9.py
MIN_THROTTLE = 1520  # Already fixed
MAX_THROTTLE = 1700  # Increase this
```

### Fix 2: Verify Channel Mapping
Test manually in Mission Planner first, then update script if needed.

### Fix 3: Check RC Override Timeout
```python
# Ensure commands sent faster than 3 seconds
# Current: 10Hz (0.1s) - this is fine
```

### Fix 4: Add Debug Output
The script already shows:
- `Steer:XXXX` - current steering command
- `Throttle:XXXX` - current throttle command
- `TX:XXXX` - command count (should increase)

Watch these values - if they're changing but rover doesn't move, it's a hardware/channel issue.

---

## Expected Behavior

**When Clear Path:**
```
Steer:1500 Throttle:1650  (straight, forward)
```

**When Obstacle Detected:**
```
Steer:1640 Throttle:1520  (turn right, slow)
```

**When Obstacle Too Close:**
```
Steer:1500 Throttle:1500  (stop)
```

---

## Still Not Working?

1. **Test RC Override Manually First**
   - Mission Planner → Actions → Override RC Channels
   - If manual override doesn't work, RC override isn't configured correctly

2. **Check Physical RC Connection**
   - If physical RC is connected, it might override MAVLink commands
   - Disconnect physical RC or set `RC_OVERRIDE_TIME` appropriately

3. **Verify Rover Hardware**
   - Motors connected?
   - ESC calibrated?
   - Battery voltage OK?

4. **Check ArduPilot Logs**
   - Mission Planner → Data → Logs
   - Look for RC override messages or errors

---

## Summary

Most common issues:
1. **Throttle too low** - Fixed (now 1520-1650)
2. **Wrong channel mapping** - Verify in Mission Planner
3. **RC override not enabled** - Check `RC_OVERRIDE_TIME = 3`
4. **Rover not armed** - Must be ARMED
5. **Wrong mode** - Must be GUIDED or MANUAL

