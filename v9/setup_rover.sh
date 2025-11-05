#!/usr/bin/env bash
set -euo pipefail

# Project Astra NZ - Rover Setup (Ubuntu)
# Purpose:
#   Prepare the rover runtime once, then you can run the manager separately.
#   - Creates/uses ~/rover_venv (Python virtual environment)
#   - Installs Python dependencies from v9/requirements.txt into that venv
#   - Verifies critical imports (numpy, pyrealsense2)
#   - Prints the exact activation and run commands at the end

echo "[setup] Starting rover setup (Ubuntu)"

VENV_DIR="$HOME/rover_venv"
REQ_FILE="$(dirname "$0")/requirements.txt"

# 1) Ensure base system packages are available
echo "[setup] Ensuring system packages present (python3, venv, pip)"
set +e  # Allow apt-get to fail partially
sudo apt-get update -y 2>&1 | grep -v "librealsense" || true
set -e
sudo apt-get install -y python3 python3-pip python3-venv ca-certificates build-essential libgl1 curl gnupg lsb-release

# 1a) Add user to dialout for serial (Pixhawk/LiDAR)
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx "dialout"; then
  echo "[setup] Adding $USER to dialout group (for /dev/ttyUSB*, /dev/ttyACM*)"
  sudo usermod -aG dialout "$USER" || true
  echo "[setup] NOTE: You must log out and log back in for dialout group changes to take effect."
fi

# 2) Create venv if missing (idempotent)
if [ ! -d "$VENV_DIR" ]; then
  echo "[setup] Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
else
  echo "[setup] Using existing venv at $VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

# 3) Upgrade pip toolchain inside the venv
echo "[setup] Upgrading pip/setuptools/wheel"
"$VENV_PY" -m pip install -U pip setuptools wheel

# 4) Install project Python dependencies into the venv
if [ -f "$REQ_FILE" ]; then
  echo "[setup] Installing Python requirements from $REQ_FILE"
  "$VENV_PIP" install -r "$REQ_FILE"
else
  echo "[setup] WARNING: requirements.txt not found at $REQ_FILE"
fi

# 4a) Install Intel RealSense system libraries if missing (tools like rs-enumerate-devices)
if ! command -v rs-enumerate-devices >/dev/null 2>&1; then
  echo "[setup] Intel RealSense tools not found; attempting to install librealsense packages"
  # Remove any existing librealsense repo that might be misconfigured
  sudo rm -f /etc/apt/sources.list.d/librealsense*.list 2>/dev/null || true
  
  # Add Intel RealSense apt repository (official) - try with error handling
  set +e
  sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE >/dev/null 2>&1
  UBUNTU_CODENAME=$(lsb_release -cs)
  echo "deb https://librealsense.intel.com/Debian/apt-repo ${UBUNTU_CODENAME} main" | sudo tee /etc/apt/sources.list.d/librealsense.list >/dev/null
  
  # Update apt, but ignore librealsense errors
  sudo apt-get update -y 2>&1 | grep -v "librealsense" || true
  
  # Try to install, but don't fail if repo doesn't work
  sudo apt-get install -y librealsense2-dkms librealsense2-utils librealsense2-dev 2>&1 | grep -v "librealsense" || true
  set -e
  
  if command -v rs-enumerate-devices >/dev/null 2>&1; then
    echo "[setup] ✓ librealsense utilities installed"
  else
    echo "[setup] ⚠ Could not install librealsense utilities automatically."
    echo "[setup] ⚠ This is OK - pyrealsense2 Python package will work without system tools."
    echo "[setup] ⚠ If camera fails, you can install librealsense manually later."
  fi
fi

# 5) Quick import check (helps catch missing system libs or wheels)
echo "[setup] Quick import check"
set +e
"$VENV_PY" - <<'PY'
import importlib, sys
mods = [
    ('numpy', 'np'),
    ('pyrealsense2', 'rs'),
]
ok = True
for m, alias in mods:
    try:
        importlib.import_module(m)
        print(f"  ✓ {m} import OK")
    except Exception as e:
        ok = False
        print(f"  ✗ {m} import failed: {e}")
if not ok:
    sys.exit(1)
PY
rc=$?
set -e

if [ $rc -ne 0 ]; then
  echo "[setup] Some imports failed. You can retry: $VENV_PIP install -r v9/requirements.txt"
fi

echo
echo "[setup] Done. Next steps:"
echo "  1) Activate venv in your shell (optional, for manual debugging):"
echo "     source \"$VENV_DIR/bin/activate\""
echo "  2) Run the manager using the venv python (no activation needed):"
echo "     \"$VENV_DIR/bin/python3\" \"$(dirname "$0")/rover_manager_v9.py\""
echo "     or: bash \"$(dirname "$0")/run_manager.sh\""
echo "  3) If you were just added to dialout, log out and back in before running."
echo
echo "==================== COPY / PASTE COMMANDS ===================="
echo "# Activate the virtual environment (current shell)"
echo "source $VENV_DIR/bin/activate"
echo
echo "# Start the manager (uses the venv python)"
echo "$VENV_DIR/bin/python3 $(dirname "$0")/rover_manager_v9.py"
echo "# or"
echo "bash $(dirname "$0")/run_manager.sh"
echo "==============================================================="
echo
echo "[setup] Complete."


