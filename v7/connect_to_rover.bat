@echo off
echo ============================================================
echo PROJECT ASTRA NZ - ROVER CONNECTION
echo ============================================================
echo.

REM Check if ZeroTier is running
tasklist /FI "IMAGENAME eq zerotier-one.exe" 2>NUL | find /I /N "zerotier-one.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] ZeroTier is running
) else (
    echo [ERROR] ZeroTier is not running
    echo Please run setup_zerotier_windows.bat first
    pause
    exit /b 1
)

echo.
echo [1/3] Checking ZeroTier network status...
"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" listnetworks

echo.
echo [2/3] Testing rover connectivity...
ping -n 1 172.25.133.85 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover is reachable at 172.25.133.85
) else (
    echo [WARNING] Rover not reachable - trying alternative IP...
    ping -n 1 172.25.77.186 >nul 2>&1
    if %errorLevel% equ 0 (
        echo [OK] Rover is reachable at 172.25.77.186
        set ROVER_IP=172.25.77.186
    ) else (
        echo [WARNING] Rover not reachable - checking network status...
        echo Please ensure:
        echo 1. ZeroTier network is authorized
        echo 2. Rover is running and connected
        echo 3. Network ID: 4753cf475f287023
        pause
        exit /b 1
    )
)

echo.
echo [3/3] Starting dashboard connection...
echo.
echo ============================================================
echo ROVER DASHBOARD ACCESS
echo ============================================================
echo.
if not defined ROVER_IP set ROVER_IP=172.25.133.85
echo Rover IP: %ROVER_IP%
echo Dashboard URL: http://%ROVER_IP%:8081
echo.
echo Opening dashboard in your default browser...
echo.

REM Open dashboard in default browser
start http://%ROVER_IP%:8081

echo.
echo Dashboard opened! If it doesn't load:
echo 1. Check if rover is running: python3 rover_manager_v7.py
echo 2. Check if dashboard is running: python3 telemetry_dashboard_v7.py
echo 3. Verify ZeroTier network authorization
echo.
echo Press any key to exit...
pause >nul
