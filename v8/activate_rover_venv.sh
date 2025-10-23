#!/bin/bash
"""
Project Astra NZ - Rover Virtual Environment Activator
Simple script to activate the rover virtual environment
"""

VENV_PATH="$HOME/rover_venv"
ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"

echo "Project Astra NZ - Virtual Environment Activator"
echo "================================================"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "Please run: python3 rover_setup_v9.py"
    exit 1
fi

if [ ! -f "$ACTIVATE_SCRIPT" ]; then
    echo "❌ Activation script not found: $ACTIVATE_SCRIPT"
    echo "Virtual environment may be corrupted"
    exit 1
fi

echo "✅ Virtual environment found at: $VENV_PATH"
echo "🔧 Activating virtual environment..."
echo ""

# Source the activation script
source "$ACTIVATE_SCRIPT"

echo "✅ Virtual environment activated!"
echo "🐍 Python path: $(which python3)"
echo "📦 Pip path: $(which pip)"
echo ""
echo "You can now run:"
echo "  python3 rover_manager_v9.py"
echo ""
echo "To deactivate, run: deactivate"
echo ""

# Keep the shell active with the virtual environment
exec bash
