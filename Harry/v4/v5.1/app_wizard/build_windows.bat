@echo off
REM Build single EXE with PyInstaller
setlocal

REM Change to repo root (one level up from this script)
pushd "%~dp0\.."
echo Building from: %CD%

REM Ensure PyInstaller is available
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
  echo Installing PyInstaller...
  python -m pip install pyinstaller
)

REM Clean previous build artifacts
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist AstraWizard.spec del /f /q AstraWizard.spec

REM Build EXE (Windows uses ';' in --add-data)
python -m PyInstaller --noconfirm --onefile --name AstraWizard --add-data "app_wizard;app_wizard" -p . app_wizard\main.py

echo.
if exist dist\AstraWizard.exe (
  echo Copying required scripts next to EXE...
  copy /y combo_proximity_bridge_v4.py dist\ >nul
  copy /y rover_data_relay_v4.py dist\ >nul
  echo Done. Find EXE under %CD%\dist\AstraWizard.exe
) else (
  echo Build finished but EXE not found in dist. Check build logs above.
)

popd


