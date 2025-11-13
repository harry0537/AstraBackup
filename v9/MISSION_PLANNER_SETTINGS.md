# Mission Planner Settings for Obstacle-Based Navigation

## Required Settings for `obstacle_navigation_v9.py`

### 1. Flight Mode

**REQUIRED: MANUAL Mode (for RC override without GPS)**
- **Use MANUAL mode for obstacle navigation without GPS waypoints**
- GUIDED mode requires GPS waypoints/position targets
- MANUAL mode accepts RC override directly
- No GPS needed - perfect for indoor testing

**NOT Recommended: GUIDED Mode**
- GUIDED mode expects GPS waypoints or position targets
- RC override may not work properly without active mission
- Use GUIDED only if you have GPS waypoints

**Why MANUAL?**
- Direct RC control via MAVLink
- No waypoint requirements
- Works perfectly for obstacle-based navigation

**NOT Recommended: AUTO Mode**
- Will try to follow waypoints
- May conflict with obstacle navigation

### 2. RC Override Settings

**Enable RC Override:**
- Mission Planner → Config/Tuning → Standard Params
- Find `SERIALx_PROTOCOL` (where x is your telemetry port)
- Ensure it's set to `2` (MAVLink 2) or `1` (MAVLink 1)
- RC override works automatically with MAVLink connection

**Verify RC Override Works:**
- In Mission Planner, go to Flight Data → Actions
- Try "Override RC Channels" manually
- If it works, your navigation script will work too

### 3. Obstacle Avoidance Parameters

**Critical Parameters (Set in Mission Planner → Config/Tuning → Full Parameter List):**

| Parameter | Value | Description |
|-----------|-------|-------------|
| `AVOID_ENABLE` | `7` | Enable all avoidance types (bitmask: 1=Proximity, 2=GPS, 4=Beacon) |
| `AVOID_MARGIN` | `150` | Stop distance in cm (1.5m - matches navigation script) **Note: Baseline has 30cm, change to 150cm** |
| `PRX1_TYPE` | `2` | Use MAVLink proximity sensors (from proximity bridge) |
| `PRX1_ORIENT` | `0` | Orientation (0=forward, adjust if needed) |
| `PRX1_YAW_OFFSET` | `0` | Yaw offset if sensor not aligned |
| `OA_TYPE` | `1` | Obstacle avoidance type: 1=Bendy Ruler, 2=Simple |
| `OA_BR_LOOKAHEAD` | `500` | Lookahead distance in cm (5m) |
| `OA_BR_LOOKAHEAD_OVR` | `0` | Override lookahead (0=disabled) |

**Optional but Recommended:**
| Parameter | Value | Description |
|-----------|-------|-------------|
| `PRX_LOG` | `1` | Log proximity data for debugging |
| `AVOID_BEHAVE` | `1` | Behavior: 1=Stop, 2=Backup, 3=Backup and turn |
| `AVOID_BACKUP_SPD` | `75` | Backup speed in cm/s (0.75 m/s) |
| `AVOID_ACCEL_MAX` | `300` | Max avoidance acceleration in cm/s² |

### 4. Safety Settings

**Geofence (Optional but Recommended):**
- Mission Planner → Config/Tuning → Geofence
- Set max radius if you want to limit rover range
- Set action: `0`=Report only, `1`=Guided mode, `2`=RTL, `3`=Stop

**Battery Safety:**
- Set low battery warning/action if using battery monitoring
- Mission Planner → Config/Tuning → Battery

**E-Stop:**
- Mission Planner → Flight Data → Actions → Emergency Stop
- Keep this available for emergency stops

### 5. RC Channel Mapping

**Verify Channel Assignment:**
- Mission Planner → Config/Tuning → Radio Calibration
- **Channel 1**: Should be Steering
- **Channel 3**: Should be Throttle (typical rover setup)

**If channels are different:**
- Note which channels control steering/throttle
- Update `obstacle_navigation_v9.py` `send_rc_override()` method accordingly

### 6. Telemetry Settings

**Serial Port Configuration:**
- Mission Planner → Config/Tuning → Planner
- Ensure telemetry port is configured for MAVLink
- Baud rate: `57600` (or match your setup)

**UDP Connection (if using):**
- Mission Planner → Connect → UDP
- Port: `14550` (default)
- This allows multiple connections (proximity bridge + Mission Planner)

### 7. Arming Settings

**Arming Requirements:**
- Mission Planner → Config/Tuning → Safety
- `ARMING_CHECK`: Set to `1` (basic checks) or `0` (disable for testing)
- Ensure rover can arm before navigation starts

**Pre-Arm Checklist:**
- GPS lock (if using GPS)
- Battery voltage OK
- No safety switch issues
- Proximity sensors detected (check Mission Planner → Proximity tab)

## Step-by-Step Setup

### Initial Setup

1. **Connect to Rover**
   - Mission Planner → Connect → Serial (or UDP)
   - Select correct port/baud rate
   - Wait for heartbeat

2. **Load Parameters**
   - Mission Planner → Config/Tuning → Full Parameter List
   - Set all parameters from section 3 above
   - Click "Write Params" to save

3. **Reboot Pixhawk**
   - Mission Planner → Actions → Reboot Pixhawk
   - Wait for reconnection

4. **Verify Proximity Sensors**
   - Mission Planner → Flight Data → Proximity tab
   - Should see 8 sectors updating (if proximity bridge is running)
   - Values should update at ~10Hz

5. **Test RC Override**
   - Mission Planner → Flight Data → Actions
   - Try "Override RC Channels" manually
   - Set Channel 1 (steering) and Channel 3 (throttle)
   - Verify rover responds

6. **Set Flight Mode**
   - Mission Planner → Flight Data → Mode
   - Select **GUIDED** mode
   - Arm the rover

7. **Start Navigation**
   - On rover: `python3 obstacle_navigation_v9.py`
   - Watch Mission Planner → Flight Data → RC Override status
   - Should see channels updating

## Verification Checklist

Before running obstacle navigation:

- [ ] Pixhawk connected and heartbeat received
- [ ] Proximity sensors visible in Mission Planner (8 sectors)
- [ ] RC override tested and working
- [ ] Flight mode set to GUIDED (or MANUAL)
- [ ] Rover armed
- [ ] `AVOID_ENABLE = 7` (or at least `1` for proximity)
- [ ] `PRX1_TYPE = 2` (MAVLink proximity)
- [ ] `AVOID_MARGIN = 150` (1.5m stop distance)
- [ ] Proximity bridge running (`combo_proximity_bridge_v9.py`)
- [ ] Navigation script running (`obstacle_navigation_v9.py`)

## Troubleshooting

### "RC Override Not Working"
- Check `SERIALx_PROTOCOL` is set to MAVLink (1 or 2)
- Verify you're in GUIDED or MANUAL mode (not AUTO)
- Check Mission Planner → Flight Data → RC Override shows activity
- Ensure no other RC override is active

### "Proximity Sensors Not Showing"
- Verify proximity bridge is running: `ps aux | grep combo_proximity_bridge`
- Check proximity data file: `cat /tmp/proximity_v9.json`
- Verify `PRX1_TYPE = 2` (MAVLink proximity)
- Check Mission Planner → Proximity tab (should show 8 sectors)

### "Rover Not Responding to Commands"
- Check rover is armed
- Verify flight mode (GUIDED or MANUAL)
- Check RC channel mapping (Channel 1 = Steering, Channel 3 = Throttle)
- Test manual RC override in Mission Planner first

### "Rover Stops Immediately"
- Check `AVOID_MARGIN` - might be too large
- Verify proximity sensors are reading correctly (not all at 0cm)
- Check obstacle navigation script is sending commands
- Look at Mission Planner → Messages for errors

### "Rover Drives Wrong Direction"
- Check RC channel mapping
- Verify steering direction in Mission Planner → Radio Calibration
- May need to reverse steering channel or adjust sector mapping

## Advanced Configuration

### Dual-Layer Obstacle Avoidance

The system has two layers:
1. **ArduPilot Built-in** (if `AVOID_ENABLE` is set): Uses proximity data for automatic avoidance
2. **Navigation Script**: Uses proximity data for reactive steering

**Recommendation:**
- For pure script control: Set `AVOID_ENABLE = 0` (disable ArduPilot avoidance)
- For safety backup: Set `AVOID_ENABLE = 7` (both work together, ArduPilot as backup)

### Speed Control

Adjust navigation script parameters:
- `MAX_THROTTLE = 1600`: Maximum forward speed
- `MIN_THROTTLE = 1400`: Minimum forward speed
- `SAFE_DISTANCE_CM = 150`: Stop distance (1.5m)
- `CAUTION_DISTANCE_CM = 300`: Slow down distance (3.0m)

Match `AVOID_MARGIN` in ArduPilot to `SAFE_DISTANCE_CM` in script for consistency.

## Quick Reference

**Minimum Required Settings:**
```
AVOID_ENABLE = 7 (or 0 if using script-only)
PRX1_TYPE = 2
Flight Mode = GUIDED or MANUAL
RC Override = Enabled (automatic with MAVLink)
```

**Recommended Settings:**
```
AVOID_ENABLE = 7
AVOID_MARGIN = 150
PRX1_TYPE = 2
OA_TYPE = 1
OA_BR_LOOKAHEAD = 500
Flight Mode = GUIDED
```

## See Also

- `v9/OBSTACLE_NAVIGATION_GUIDE.md`: Navigation script usage
- `v9/config/rover_baseline_v9.param`: Baseline parameter file
- ArduPilot Rover Documentation: Obstacle Avoidance

