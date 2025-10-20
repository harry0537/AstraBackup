@echo off
echo ============================================================
echo PROJECT ASTRA NZ - ROVER CONNECTION TEST
echo ============================================================
echo.

echo [1/4] Checking ZeroTier status...
"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" listnetworks

echo.
echo [2/4] Testing rover connectivity...
echo Testing 172.25.133.85...
ping -n 1 172.25.133.85 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover reachable at 172.25.133.85
    set ROVER_IP=172.25.133.85
    goto :test_dashboard
)

echo Testing 172.25.77.186...
ping -n 1 172.25.77.186 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover reachable at 172.25.77.186
    set ROVER_IP=172.25.77.186
    goto :test_dashboard
)

echo [ERROR] Rover not reachable on either IP
echo Please check:
echo 1. ZeroTier network authorization
echo 2. Rover is running
echo 3. Network connectivity
pause
exit /b 1

:test_dashboard
echo.
echo [3/4] Testing dashboard access...
echo Testing http://%ROVER_IP%:8081...

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%ROVER_IP%:8081' -TimeoutSec 5; if ($response.StatusCode -eq 200) { Write-Host '[OK] Dashboard accessible' -ForegroundColor Green; exit 0 } else { Write-Host '[ERROR] Dashboard returned status' $response.StatusCode -ForegroundColor Red; exit 1 } } catch { Write-Host '[ERROR] Cannot connect to dashboard' -ForegroundColor Red; exit 1 }"

if %errorLevel% equ 0 (
    echo [OK] Dashboard is accessible
) else (
    echo [ERROR] Dashboard not accessible
    echo Please check if rover services are running
    pause
    exit /b 1
)

echo.
echo [4/4] Opening dashboard...
echo.
echo ============================================================
echo ROVER DASHBOARD ACCESS
echo ============================================================
echo.
echo Rover IP: %ROVER_IP%
echo Dashboard URL: http://%ROVER_IP%:8081
echo.
echo Opening dashboard in your browser...
start http://%ROVER_IP%:8081

echo.
echo [SUCCESS] Dashboard opened!
echo.
echo If the dashboard doesn't load:
echo 1. Check if rover is running: python3 rover_manager_v7.py
echo 2. Check if dashboard is running: python3 telemetry_dashboard_v7.py
echo 3. Verify ZeroTier network authorization
echo.
pause
