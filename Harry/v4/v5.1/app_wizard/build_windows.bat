@echo off
REM Build single EXE with PyInstaller
setlocal
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
  echo Installing PyInstaller...
  python -m pip install pyinstaller
)

pyinstaller --onefile --name AstraWizard --add-data "app_wizard;app_wizard" -p . app_wizard\main.py
echo Done. Find EXE under dist\AstraWizard.exe


