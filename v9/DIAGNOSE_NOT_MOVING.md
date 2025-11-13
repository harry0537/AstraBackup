# Diagnose: Rover Not Moving

## Quick Diagnostic Steps

### Step 1: Test RC Override Directly

Run the test script to verify RC override works:

```bash
cd /path/to/AstraBackup/v9
python3 test_rc_override.py
```

**What it does:**
- Connects to Pixhawk
- Sends test commands (forward, turn, stop)
- Tests different throttle values

**Expected:**
- Rover should move forward, turn, stop
- If it moves, RC override works - problem is in navigation script
- If it doesn't move, problem is hardware/channel mapping

---

### Step 2: Check Current Status

**In Mission Planner:**
1. **Check Mode:**
   - Flight Data → Mode
   - Should show "GUIDED" or "MANUAL"
   - If "AUTO" or "HOLD", change to GUIDED

2. **Check Armed Status:**
   - Should show "ARMED" (you confirmed this)

3. **Check RC Channels:**
   - Flight Data → Radio Calibration
   - Move physical RC sticks
   - Note which channels move for steering/throttle
   - **If physical RC is connected, it might override MAVLink commands**

4. **Check RC Override:**
   - Flight Data → Actions → "Override RC Channels"
   - Manually set Channel 3 = 1650
   - Does rover move? If yes, RC override works

---

### Step 3: Verify Channel Mapping

**Common ArduPilot Rover Channel Mapping:**
- Channel 1: Steering (Yaw)
- Channel 2: Throttle (some rovers)
- Channel 3: Throttle (other rovers)

**Check Your Setup:**
1. Mission Planner → Config/Tuning → Radio Calibration
2. Move physical steering stick → which channel moves?
3. Move physical throttle stick → which channel moves?

**If different from script:**
- Edit `obstacle_navigation_v9.py`
- In `send_rc_override()`, change channel positions:
  ```python
  self.mavlink.mav.rc_channels_override_send(
      ...
      steering_pwm,  # Change channel number if needed
      ...
      throttle_pwm,  # Change channel number if needed
      ...
  )
  ```

---

### Step 4: Check Physical RC Connection

**Problem:** If physical RC transmitter is connected and sending signals, it will override MAVLink commands.

**Fix:**
1. **Disconnect physical RC** (if possible)
2. **Or set RC override timeout:**
   - Mission Planner → Config/Tuning → Full Parameter List
   - `RC_OVERRIDE_TIME = 3` (should be 3, not 0)
   - This allows MAVLink to override physical RC

**Verify:**
- Mission Planner → Flight Data → RC Channels
- If channels are moving without physical input, physical RC is active
- RC override should still work, but might conflict

---

### Step 5: Check ESC/Motor Calibration

**Problem:** Motors not calibrated or ESC not responding

**Test:**
1. Disconnect from navigation script
2. Use physical RC (if available)
3. Does rover move with physical RC?
   - If NO: Hardware issue (ESC, motors, wiring)
   - If YES: RC override or channel mapping issue

---

### Step 6: Check Navigation Script Output

**Watch the navigation script:**
```bash
python3 obstacle_navigation_v9.py
```

**Look for:**
- `Throttle:1650` when path is clear (should move)
- `Throttle:1500` when obstacle detected (stops)
- `TX:XXXX` increasing (commands being sent)

**If throttle is 1650 but rover doesn't move:**
- RC override not working or wrong channel
- Try test script first

**If throttle is stuck at 1500:**
- Obstacles too close (check proximity data)
- Navigation script thinks it should stop

---

### Step 7: Check Proximity Data

**Verify obstacles aren't blocking:**
```bash
cat /tmp/proximity_v9.json | python3 -m json.tool
```

**Look for:**
- `sectors_cm`: Array of 8 distances
- If all values are `2500` (max), no obstacles detected
- If values are low (e.g., `75`, `97`), obstacles detected

**If obstacles detected:**
- Navigation script will stop (`Throttle:1500`)
- Move rover to open area or adjust `SAFE_DISTANCE_CM`

---

### Step 8: Increase Throttle Further

**If test script works but navigation doesn't:**

Edit `obstacle_navigation_v9.py`:
```python
MAX_THROTTLE = 1700  # Increase from 1650
# or even
MAX_THROTTLE = 1750
```

Some rovers need higher throttle to overcome friction/dead zone.

---

## Common Issues Summary

| Issue | Symptom | Fix |
|-------|---------|-----|
| Wrong channel | Commands sent but no movement | Check channel mapping, update script |
| Physical RC active | RC override ignored | Disconnect RC or set `RC_OVERRIDE_TIME` |
| Throttle too low | Commands sent but no movement | Increase `MAX_THROTTLE` to 1700-1750 |
| Obstacles detected | Throttle stuck at 1500 | Move to open area or adjust `SAFE_DISTANCE_CM` |
| ESC not calibrated | No movement at all | Calibrate ESC or check hardware |
| Wrong mode | Commands rejected | Set mode to GUIDED or MANUAL |
| Not armed | Commands ignored | ARM the rover |

---

## Diagnostic Order

1. **Run test script** (`test_rc_override.py`)
   - If works: Problem in navigation script
   - If doesn't work: Hardware/channel issue

2. **Test manual RC override** (Mission Planner)
   - If works: RC override enabled, check script
   - If doesn't work: RC override not enabled or wrong mode

3. **Check channel mapping**
   - Verify which channels control steering/throttle
   - Update script if different

4. **Check physical RC**
   - Disconnect if possible
   - Or verify RC override timeout set

5. **Check navigation script output**
   - Watch throttle values
   - Verify commands being sent

---

## Next Steps

After running `test_rc_override.py`, report:
- Did rover move during test?
- Which test commands worked?
- What throttle value made it move?

This will help identify the exact issue.

