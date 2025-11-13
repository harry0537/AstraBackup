# Fix MAVLink Communication Issues

## Problem: Bad Packets and CRC Failures

Mission Planner is showing:
- `Bad Packet (crc fail)`
- `pkts lost 38, 10, 9, 6...`
- `Unknown Packet` messages

## Solutions

### 1. Check Serial Port Baud Rate

**Issue:** Baud rate mismatch causes packet corruption

**Fix:**
- Mission Planner → Config/Tuning → Planner
- Check `SERIALx_BAUD` matches your connection
- Common: `57600` or `115200`
- **Both Mission Planner AND proximity bridge must use same baud rate**

### 2. Reduce MAVLink Message Rate

**Issue:** Too many messages = packet loss

**Fix in Mission Planner:**
- Mission Planner → Config/Tuning → Planner
- Set `SRx_ADSB` = `0` (disable if not needed)
- Set `SRx_EXT_STAT` = `2` (reduce rate)
- Set `SRx_EXTRA1` = `5` (reduce rate)
- Set `SRx_EXTRA2` = `2` (reduce rate)
- Set `SRx_EXTRA3` = `2` (reduce rate)
- Set `SRx_PARAMS` = `10` (reduce rate)
- Set `SRx_POSITION` = `3` (reduce rate)
- Set `SRx_RAW_SENS` = `2` (reduce rate)
- Set `SRx_RC_CHAN` = `2` (reduce rate)

**Or use script to set rates:**
```python
# Connect and set lower rates
from pymavlink import mavutil
mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=57600)
mav.wait_heartbeat()

# Set message intervals (in microseconds, 1000000 = 1Hz)
rates = {
    'ATTITUDE': 200000,      # 5Hz
    'GPS_RAW_INT': 200000,   # 5Hz
    'RC_CHANNELS': 100000,   # 10Hz
    'SYS_STATUS': 1000000,   # 1Hz
}

for msg_name, interval in rates.items():
    msg_id = mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE  # Example
    mav.mav.request_data_stream_send(
        mav.target_system, mav.target_component,
        msg_id, interval, 1  # 1 = start
    )
```

### 3. Use UDP Instead of Serial (Recommended)

**Issue:** Serial port conflicts or USB issues

**Fix:**
- Use MAVProxy or UDP bridge
- Mission Planner → Connect → UDP (port 14550)
- Proximity bridge can use serial
- Mission Planner uses UDP (no conflict)

**Setup UDP Bridge:**
```bash
# On rover, start MAVProxy
mavproxy.py --master=/dev/ttyACM0 --baud=57600 --out=udp:0.0.0.0:14550

# In Mission Planner
# Connect → UDP → Port 14550
```

### 4. Check USB Cable/Port

**Issue:** Bad USB connection causes corruption

**Fix:**
- Try different USB port
- Use shorter, higher quality USB cable
- Avoid USB hubs (connect directly)
- Check USB port power (use powered hub if needed)

### 5. Disable GPS Requirement for Arming

**Issue:** "GPS Bad fix" prevents arming

**Fix:**
- Mission Planner → Config/Tuning → Safety
- Set `ARMING_CHECK` = `1` (basic checks only)
- Or set `ARMING_CHECK` = `0` (disable for testing)
- Set `ARMING_RUDDER` = `2` (allow arming without GPS)

**Or set parameter:**
```
ARMING_CHECK = 1  (or 0 for testing)
ARMING_RUDDER = 2
```

### 6. Reduce Proximity Bridge Update Rate

**Issue:** Too many proximity messages = packet loss

**Fix in `combo_proximity_bridge_v9.py`:**
```python
# In fuse_and_send(), reduce rate
# Change from 0.1 (10Hz) to 0.2 (5Hz)
if time.time() - last_send > 0.2:  # Was 0.1
    self.fuse_and_send()
    last_send = time.time()
```

### 7. Check for Multiple MAVLink Connections

**Issue:** Multiple scripts using same port = conflicts

**Fix:**
```bash
# Check what's using the port
lsof /dev/ttyACM0
# or
fuser /dev/ttyACM0

# Kill duplicate connections
pkill -f mavlink
```

## Quick Fixes (Try These First)

### Option 1: Use UDP Connection
```bash
# Terminal 1: Start MAVProxy bridge
mavproxy.py --master=/dev/ttyACM0 --baud=57600 --out=udp:0.0.0.0:14550

# Mission Planner: Connect → UDP → Port 14550
```

### Option 2: Reduce Message Rates
Mission Planner → Config/Tuning → Planner → Set all `SRx_*` to `2` or `5`

### Option 3: Disable GPS Arming Check
Mission Planner → Config/Tuning → Safety → `ARMING_CHECK = 1` (or `0` for testing)

## Verification

After fixes:
1. Mission Planner logs should show fewer "Bad Packet" errors
2. Packet loss should decrease
3. Rover should stay armed
4. Navigation commands should be received reliably

## If Still Having Issues

1. **Check serial port permissions:**
   ```bash
   sudo usermod -a -G dialout $USER
   # Logout and login again
   ```

2. **Try different baud rate:**
   - Change both Mission Planner and proximity bridge to `115200`

3. **Check for USB power issues:**
   - Use powered USB hub
   - Try different USB port

4. **Monitor MAVLink traffic:**
   ```bash
   # Watch for errors
   dmesg | grep ttyACM
   ```

