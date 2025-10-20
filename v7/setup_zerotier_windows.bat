@echo off
echo ============================================================
echo PROJECT ASTRA NZ - ZEROTIER WINDOWS SETUP
echo ============================================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script must be run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo [1/4] Installing ZeroTier...
echo.

REM Download and install ZeroTier
echo Downloading ZeroTier...
powershell -Command "Invoke-WebRequest -Uri 'https://download.zerotier.com/RELEASES/1.16.0/dist/ZeroTier%20One.msi' -OutFile 'ZeroTier.msi'"

if exist ZeroTier.msi (
    echo Installing ZeroTier...
    msiexec /i ZeroTier.msi /quiet
    timeout /t 5 /nobreak >nul
    del ZeroTier.msi
    echo [OK] ZeroTier installed
) else (
    echo [ERROR] Failed to download ZeroTier
    pause
    exit /b 1
)

echo.
echo [2/4] Starting ZeroTier service...
net start ZeroTierOne
timeout /t 3 /nobreak >nul

echo.
echo [3/4] Joining ZeroTier network...
echo Network ID: 4753cf475f287023
"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" join 4753cf475f287023

echo.
echo [4/4] Waiting for network connection...
echo Please wait while ZeroTier connects to the network...
timeout /t 10 /nobreak >nul

echo.
echo ============================================================
echo SETUP COMPLETE
echo ============================================================
echo.
echo ZeroTier network joined successfully!
echo Rover IP: 172.25.77.186
echo Dashboard: http://172.25.77.186:8081
echo.
echo Next steps:
echo 1. Wait for network authorization (check ZeroTier web interface)
echo 2. Run: connect_to_rover.bat
echo.
pause
