#!/usr/bin/env bash
# Project Astra NZ - Apply Parameters Script
# Applies rover_baseline_v9.param to Pixhawk

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/rover_venv"
PARAM_FILE="$SCRIPT_DIR/config/rover_baseline_v9.param"
BACKUP_FILE="/tmp/pixhawk_backup_$(date +%Y%m%d_%H%M%S).param"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[ERROR] Virtual environment not found at $VENV_DIR"
    echo "  Run setup_rover.sh first to create the venv"
    exit 1
fi

VENV_PY="$VENV_DIR/bin/python3"

# Check if param file exists
if [ ! -f "$PARAM_FILE" ]; then
    echo "[ERROR] Parameter file not found: $PARAM_FILE"
    exit 1
fi

# Detect Pixhawk port
PIXHAWK_PORT="/dev/ttyACM0"
if [ ! -e "$PIXHAWK_PORT" ]; then
    # Try alternative ports
    for port in /dev/ttyACM{1..3}; do
        if [ -e "$port" ]; then
            PIXHAWK_PORT="$port"
            break
        fi
    done
    
    if [ ! -e "$PIXHAWK_PORT" ]; then
        echo "[ERROR] Pixhawk not found on /dev/ttyACM*"
        echo "  Make sure Pixhawk is connected via USB"
        exit 1
    fi
fi

echo "[INFO] Found Pixhawk at: $PIXHAWK_PORT"
echo "[INFO] Parameter file: $PARAM_FILE"
echo "[INFO] Backup will be saved to: $BACKUP_FILE"
echo ""
read -p "Press Enter to continue, or Ctrl+C to cancel..."

# Apply parameters
echo ""
echo "[INFO] Applying parameters..."
"$VENV_PY" "$SCRIPT_DIR/tools/apply_params.py" \
    --port "$PIXHAWK_PORT" \
    --baud 57600 \
    --file "$PARAM_FILE" \
    --backup "$BACKUP_FILE" \
    --reboot

echo ""
echo "[DONE] Parameters applied. Pixhawk will reboot automatically."

