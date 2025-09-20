#!/usr/bin/env bash
set -euo pipefail

if ! command -v pyinstaller >/dev/null 2>&1; then
  python3 -m pip install --user pyinstaller
fi

pyinstaller --onefile --name astra-wizard --add-data "app_wizard:app_wizard" -p . app_wizard/main.py
echo "Done. Binary at dist/astra-wizard"
echo "Copying required scripts next to binary..."
cp -f combo_proximity_bridge_v4.py dist/ || true
cp -f rover_data_relay_v4.py dist/ || true


