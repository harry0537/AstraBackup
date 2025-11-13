# Startup Sequence for Obstacle Navigation

## Correct Order of Operations

### Step 1: Start Rover Manager
**Terminal 1:**
```bash
cd /path/to/AstraBackup/v9
python3 rover_manager_v9.py
```

**Wait for:**
- All components show `✓ RUNNING`
- Proximity Bridge operational
- Proximity data showing in status (e.g., "Closest: 75cm")

**Expected output:**
```
PROJECT ASTRA NZ - Component Status V9
============================================================
Component            Status       PID      Uptime        Restarts
------------------------------------------------------------
Vision Server        ✓ RUNNING    7391     0:02:29       0
Proximity Bridge     ✓ RUNNING    7453     0:01:55       0
Data Relay           ✓ RUNNING    7424     0:02:13       0
Crop Monitor         ✓ RUNNING    7432     0:02:07       0
Dashboard            ✓ RUNNING    7436     0:02:01       0
------------------------------------------------------------

Proximity: 341 97 89 2500 2500 75 2500 231 cm
Closest: 75cm | Age: 0.1s | TX: 8256
✓ 5/8 sectors detecting obstacles
```

---

### Step 2: Start Obstacle Navigation Script
**Terminal 2 (NEW TERMINAL):**
```bash
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py
```

**Wait for:**
- `✓ Pixhawk connected`
- `✓ Proximity data available`
- `[OK] Navigation system operational`

**Expected output:**
```
============================================================
Obstacle-Based Navigation V9
============================================================
[CONFIG] Pixhawk Port: /dev/ttyACM0
[CONFIG] Proximity File: /tmp/proximity_v9.json
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

[ 45s] MAV:✓ Prox:✓ Nav:ACTIVE | Min:1.2m | Steer:1500 Throttle:1500 | TX: 450 Stops:  0
```

---

### Step 3: Configure Mission Planner

**3a. Connect to Rover:**
- Mission Planner → Connect → Serial (or UDP)
- Select correct port/baud rate
- Wait for heartbeat

**3b. Set Flight Mode to MANUAL:**
- Mission Planner → Flight Data → Mode dropdown
- Select **"MANUAL"** (NOT GUIDED - GUIDED requires GPS waypoints)
- Verify mode change successful
- **MANUAL mode is required for RC override without GPS**

**3c. Disable GPS Requirement (if needed):**
- Mission Planner → Config/Tuning → Safety
- Set `ARMING_CHECK = 1` (or `0` for testing)
- Set `ARMING_RUDDER = 2`
- Click "Write Params"
- Reboot Pixhawk (Actions → Reboot Pixhawk)

**3d. Verify Proximity Sensors:**
- Mission Planner → Flight Data → Proximity tab
- Should show 8 sectors updating
- Values should change as obstacles detected

**3e. ARM the Rover:**
- Mission Planner → Flight Data → Actions
- Click **"ARM"** button
- Verify rover shows "ARMED" status

---

## Complete Sequence Summary

```bash
# Terminal 1: Start all components
cd /path/to/AstraBackup/v9
python3 rover_manager_v9.py

# Wait for all components running, then...

# Terminal 2: Start navigation
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py

# Mission Planner: Set to GUIDED mode and ARM
```

---

## Verification Checklist

Before expecting movement:

- [ ] **Rover Manager**: All components `✓ RUNNING`
- [ ] **Proximity Bridge**: Showing obstacle data (e.g., "Closest: 75cm")
- [ ] **Navigation Script**: Shows `Nav:ACTIVE` and `MAV:✓ Prox:✓`
- [ ] **Mission Planner**: Connected and showing heartbeat
- [ ] **Mission Planner**: Mode set to **MANUAL** (not GUIDED - GUIDED requires GPS waypoints)
- [ ] **Mission Planner**: Proximity tab shows 8 sectors updating
- [ ] **Mission Planner**: Rover status shows **ARMED**
- [ ] **Navigation Script**: Commands being sent (`TX:XXXX` increasing)

---

## What Happens Next

Once all steps complete:

1. **Navigation script reads obstacles** (8 sectors)
2. **Finds best direction** (sector with most clearance)
3. **Sends steering command** (e.g., `Steer:1640` = turn right)
4. **Sends throttle command** (e.g., `Throttle:1600` = move forward)
5. **Rover moves** toward open space
6. **Stops if obstacle < 1.5m** (`Throttle:1500` = stop)

**Watch the navigation script output:**
- `Steer:1500` = going straight
- `Steer:1640` = turning right
- `Steer:1360` = turning left
- `Throttle:1500` = stopped
- `Throttle:1600` = moving forward
- `Throttle:1400` = slow forward

---

## Troubleshooting

### "Proximity data unavailable"
- Make sure Step 1 (Rover Manager) completed first
- Check proximity bridge is running in rover manager status

### "Cannot continue without Pixhawk"
- Check Pixhawk connection: `ls /dev/ttyACM*`
- Verify port in `rover_config_v9.json`

### "Rover not moving"
- Check rover is **ARMED** in Mission Planner
- Verify mode is **GUIDED** (not AUTO or MANUAL)
- Check navigation script shows `Nav:ACTIVE`
- Watch for `Steer` and `Throttle` values changing (not stuck at 1500)

### "GPS Bad fix" preventing arming
- Set `ARMING_CHECK = 1` in Mission Planner → Safety
- Set `ARMING_RUDDER = 2`
- Reboot Pixhawk
- Try arming again

---

## Quick Reference

**Order:**
1. `python3 rover_manager_v9.py` (Terminal 1)
2. `python3 obstacle_navigation_v9.py` (Terminal 2)
3. Mission Planner → **MANUAL** mode → ARM (NOT GUIDED - GUIDED requires GPS waypoints)

**That's it!** The rover will now navigate using obstacle data.

