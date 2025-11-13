# Mission Planner Quick Setup - Obstacle Navigation

## Essential Settings (5 Minutes)

### 1. Flight Mode
**Set to: GUIDED** (or MANUAL for testing)
- Mission Planner → Flight Data → Mode dropdown
- Select "GUIDED"

### 2. Critical Parameters
Mission Planner → Config/Tuning → Full Parameter List → Search and set:

```
AVOID_ENABLE = 7          (Enable obstacle avoidance)
AVOID_MARGIN = 150         (Stop at 1.5m - matches script)
PRX1_TYPE = 2            (Use MAVLink proximity sensors)
```

**Click "Write Params" → Reboot Pixhawk**

### 3. Verify Proximity Sensors
Mission Planner → Flight Data → Proximity tab
- Should show 8 sectors updating (if proximity bridge running)
- Values should change as obstacles detected

### 4. Test RC Override
Mission Planner → Flight Data → Actions → "Override RC Channels"
- Set Channel 1 (steering) to 1600
- Set Channel 3 (throttle) to 1600
- Verify rover moves
- **Reset to 0 when done testing**

### 5. Start Navigation
```bash
# On rover:
python3 obstacle_navigation_v9.py
```

## That's It!

The rover should now:
- Read obstacle data from proximity bridge
- Steer toward open space
- Stop if obstacles < 1.5m
- Drive autonomously without GPS waypoints

## Troubleshooting

**No proximity data?**
- Start proximity bridge: `python3 combo_proximity_bridge_v9.py`
- Check Mission Planner → Proximity tab

**RC override not working?**
- Must be in GUIDED or MANUAL mode (not AUTO)
- Verify rover is armed

**Rover not moving?**
- Check rover is armed
- Verify proximity sensors showing in Mission Planner
- Check navigation script is running

## Full Details
See `MISSION_PLANNER_SETTINGS.md` for complete configuration guide.

