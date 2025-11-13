# Why Use MANUAL Mode (Not GUIDED) for Obstacle Navigation

## The Problem

You're testing **indoors without GPS**, and the rover doesn't move even though:
- RC override works
- Rover is armed
- Navigation script is running
- Mode is set to GUIDED

## The Solution: Use MANUAL Mode

### GUIDED Mode Requirements

**GUIDED mode expects:**
- GPS waypoints (mission)
- Position targets (GPS coordinates)
- Active navigation mission

**GUIDED mode behavior:**
- If no waypoint/mission active, rover may not respond to RC override
- Designed for GPS-based navigation
- RC override may be ignored if no valid mission

### MANUAL Mode Benefits

**MANUAL mode is perfect for:**
- RC override without GPS
- Indoor testing
- Direct control via MAVLink
- No waypoint requirements

**MANUAL mode behavior:**
- Accepts RC override directly
- No GPS needed
- No waypoint requirements
- Direct motor control

## How to Switch

### In Mission Planner:

1. **Flight Data → Mode dropdown**
2. **Select "MANUAL"** (not GUIDED)
3. **Verify mode shows "MANUAL"**
4. **ARM the rover**
5. **Start navigation script**

## Comparison

| Mode | GPS Required | Waypoints Required | RC Override | Best For |
|------|--------------|-------------------|-------------|----------|
| **MANUAL** | ❌ No | ❌ No | ✅ Yes | **Indoor testing, obstacle navigation** |
| GUIDED | ✅ Yes | ✅ Yes | ⚠️ Maybe | GPS waypoint missions |
| AUTO | ✅ Yes | ✅ Yes | ❌ No | Autonomous missions |
| HOLD | ❌ No | ❌ No | ❌ No | Hold position |

## Why This Matters

**Your setup:**
- Indoor testing (no GPS)
- Obstacle-based navigation (no waypoints)
- RC override commands (direct control)

**MANUAL mode is the correct choice** because:
- No GPS dependency
- No waypoint requirement
- Direct RC override support
- Perfect for reactive navigation

## Quick Fix

**Change one thing:**
- Mission Planner → Mode → **MANUAL** (instead of GUIDED)

**That's it!** The rover should now respond to RC override commands.

## Verification

After switching to MANUAL mode:
1. ARM the rover
2. Start navigation script
3. Watch for `Throttle:1650` in script output
4. Rover should move forward

If it still doesn't move:
- Check throttle values in script output
- Verify RC override is working (test script)
- Check for obstacles blocking (proximity data)

---

## Summary

**For obstacle navigation without GPS:**
- ✅ Use **MANUAL** mode
- ❌ Don't use GUIDED mode (requires GPS waypoints)

**GUIDED mode is for GPS-based navigation with waypoints.**
**MANUAL mode is for direct RC control without GPS.**

