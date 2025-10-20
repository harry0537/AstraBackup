@echo off
echo ============================================================
echo PROJECT ASTRA NZ - QUICK ROVER TEST
echo ============================================================
echo.

echo [1/3] Checking ZeroTier status...
"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" listnetworks

echo.
echo [2/3] Testing rover connectivity...
echo Testing 172.25.133.85 (Rover IP)...
ping -n 1 172.25.133.85 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover reachable at 172.25.133.85
    set ROVER_IP=172.25.133.85
    goto :test_dashboard
)

echo Testing 172.25.77.186 (Alternative IP)...
ping -n 1 172.25.77.186 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover reachable at 172.25.77.186
    set ROVER_IP=172.25.77.186
    goto :test_dashboard
)

echo [ERROR] Rover not reachable on either IP
echo.
echo Troubleshooting steps:
echo 1. Make sure rover is running: python3 rover_manager_v7.py
echo 2. Check ZeroTier network authorization
echo 3. Verify network connectivity
echo.
pause
exit /b 1

:test_dashboard
echo.
echo [3/3] Testing dashboard access...
echo Testing http://%ROVER_IP%:8081...

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%ROVER_IP%:8081' -TimeoutSec 5; if ($response.StatusCode -eq 200) { Write-Host '[OK] Dashboard accessible' -ForegroundColor Green; exit 0 } else { Write-Host '[ERROR] Dashboard returned status' $response.StatusCode -ForegroundColor Red; exit 1 } } catch { Write-Host '[ERROR] Cannot connect to dashboard' -ForegroundColor Red; Write-Host 'Make sure rover services are running' -ForegroundColor Yellow; exit 1 }"

if %errorLevel% equ 0 (
    echo.
    echo ============================================================
    echo SUCCESS! DASHBOARD IS ACCESSIBLE
    echo ============================================================
    echo.
    echo Rover IP: %ROVER_IP%
    echo Dashboard URL: http://%ROVER_IP%:8081
    echo.
    echo Opening dashboard in your browser...
    start http://%ROVER_IP%:8081
    echo.
    echo [SUCCESS] Dashboard opened in your browser!
) else (
    echo.
    echo ============================================================
    echo DASHBOARD NOT ACCESSIBLE
    echo ============================================================
    echo.
    echo Please check on the rover (Ubuntu machine):
    echo 1. Run: python3 rover_manager_v7.py
    echo 2. Check if dashboard is running: ps aux ^| grep dashboard
    echo 3. Test local access: curl http://localhost:8081
    echo.
)

echo.
pause
