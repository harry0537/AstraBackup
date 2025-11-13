# Start Commands for Obstacle-Based Navigation

## Quick Start (Recommended)

### Option 1: Using the Script
```bash
cd /path/to/AstraBackup/v9
chmod +x START_OBSTACLE_NAVIGATION.sh
./START_OBSTACLE_NAVIGATION.sh
```

### Option 2: Manual Start (Two Terminals)

**Terminal 1: Proximity Bridge (REQUIRED FIRST)**
```bash
cd /path/to/AstraBackup/v9
python3 combo_proximity_bridge_v9.py
```

Wait until you see:
```
[OK] Proximity bridge operational - V9 MODE
```

**Terminal 2: Obstacle Navigation**
```bash
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py
```

---

## Using Rover Manager (Alternative)

If you want to start everything together:

**Terminal 1: Start All Components**
```bash
cd /path/to/AstraBackup/v9
python3 rover_manager_v9.py
```

Wait for all components to start, then:

**Terminal 2: Start Navigation**
```bash
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py
```

---

## Step-by-Step Manual Start

### Step 1: Start Vision Server (if not already running)
```bash
cd /path/to/AstraBackup/v9
python3 realsense_vision_server_v9.py
```
Wait 5 seconds, then proceed.

### Step 2: Start Proximity Bridge
```bash
cd /path/to/AstraBackup/v9
python3 combo_proximity_bridge_v9.py
```
Wait until you see: `[OK] Proximity bridge operational`

### Step 3: Verify Proximity Data
```bash
# Check if data file exists and is updating
cat /tmp/proximity_v9.json | python3 -m json.tool

# Or watch it update
watch -n 1 "cat /tmp/proximity_v9.json | python3 -m json.tool"
```

### Step 4: Start Navigation
```bash
cd /path/to/AstraBackup/v9
python3 obstacle_navigation_v9.py
```

---

## Expected Output

### Proximity Bridge Output:
```
============================================================
Combo Proximity Bridge V9 (NO CAMERA ACCESS)
============================================================
[CONFIG] LIDAR Port: /dev/ttyUSB0
[CONFIG] Pixhawk Port: /dev/ttyACM0
[V9] Vision Server: /tmp/vision_v9
============================================================

Waiting for Vision Server (max 30 seconds)...
✓ Vision Server detected and running
Connecting Pixhawk at /dev/ttyACM0...
✓ Pixhawk connected
[OK] LIDAR thread started
[OK] RealSense thread started (reading from Vision Server)

[OK] Proximity bridge operational - V9 MODE
```

### Navigation Script Output:
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

---

## Verification Checklist

Before starting navigation, verify:

- [ ] Mission Planner connected to rover
- [ ] Flight mode set to **GUIDED** (or MANUAL)
- [ ] Parameters set: `AVOID_ENABLE=7`, `AVOID_MARGIN=150`, `PRX1_TYPE=2`
- [ ] Pixhawk rebooted after parameter changes
- [ ] Proximity sensors visible in Mission Planner → Proximity tab (8 sectors)
- [ ] Rover is **ARMED**
- [ ] Proximity bridge running and showing data
- [ ] Navigation script started

---

## Stopping the System

**Stop Navigation:**
- Press `Ctrl+C` in navigation terminal
- Rover will automatically stop

**Stop Proximity Bridge:**
- Press `Ctrl+C` in proximity bridge terminal
- Or: `pkill -f combo_proximity_bridge_v9.py`

**Stop Everything:**
```bash
pkill -f _v9.py
```

---

## Troubleshooting

### "Proximity bridge not detected"
- Make sure `combo_proximity_bridge_v9.py` is running first
- Check: `ps aux | grep combo_proximity_bridge`
- Verify file exists: `ls -lh /tmp/proximity_v9.json`

### "Cannot continue without Pixhawk"
- Check Pixhawk connection: `ls /dev/ttyACM*`
- Verify port in `rover_config_v9.json`
- Check permissions: `sudo usermod -a -G dialout $USER` (then logout/login)

### "Proximity data unavailable"
- Start proximity bridge first
- Wait 5-10 seconds for initialization
- Check proximity bridge output for errors

### "Rover not moving"
- Verify rover is **ARMED** in Mission Planner
- Check flight mode is **GUIDED** or **MANUAL** (not AUTO)
- Verify RC override is working (test manually in Mission Planner)
- Check navigation script is sending commands (watch status output)

---

## Quick Reference

**Minimum Required:**
```bash
# Terminal 1
python3 combo_proximity_bridge_v9.py

# Terminal 2 (after Terminal 1 is running)
python3 obstacle_navigation_v9.py
```

**With Rover Manager:**
```bash
# Terminal 1
python3 rover_manager_v9.py

# Terminal 2 (after components start)
python3 obstacle_navigation_v9.py
```

---

## Next Steps

1. **Configure Mission Planner** (see `MISSION_PLANNER_QUICK_SETUP.md`)
2. **Start proximity bridge**: `python3 combo_proximity_bridge_v9.py`
3. **Verify proximity data** in Mission Planner → Proximity tab
4. **Start navigation**: `python3 obstacle_navigation_v9.py`
5. **Monitor** in Mission Planner and navigation script output

---

**Ready to drive!** The rover will now navigate using obstacle data without GPS waypoints.

