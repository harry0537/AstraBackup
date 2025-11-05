#!/usr/bin/env bash
set -euo pipefail

# Project Astra NZ - Run Manager using venv python
# What this script does:
#  1) Locates the virtual environment at ~/rover_venv
#  2) Ensures we're executing from the v9 directory (the manager uses relative paths)
#  3) Starts rover_manager_v9.py with the venv's python (no shell activation needed)

# Absolute path to this script's directory (the v9 folder)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Virtualenv location and python binary
VENV_DIR="$HOME/rover_venv"
VENV_PY="$VENV_DIR/bin/python3"

# Guard: venv must exist and contain python
if [ ! -x "$VENV_PY" ]; then
  echo "[run] venv python not found at $VENV_PY"
  echo "[run] Run setup first: bash $SCRIPT_DIR/setup_rover.sh"
  exit 1
fi

# Ensure we run from v9 directory (manager expects to find sibling scripts here)
cd "$SCRIPT_DIR"

# Exec replaces this shell with the manager process
exec "$VENV_PY" "$SCRIPT_DIR/rover_manager_v9.py"


