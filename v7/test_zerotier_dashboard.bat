@echo off
echo ============================================================
echo PROJECT ASTRA NZ - ZEROTIER DASHBOARD TEST
echo ============================================================
echo.

echo [1/3] Testing ZeroTier connectivity...
ping -n 1 172.25.133.85 >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Rover reachable at 172.25.133.85
) else (
    echo [ERROR] Rover not reachable at 172.25.133.85
    echo Please check:
    echo 1. ZeroTier is running on both devices
    echo 2. Both devices are authorized in rovernet
    echo 3. Rover services are running
    pause
    exit /b 1
)

echo.
echo [2/3] Testing dashboard access...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://172.25.133.85:8081' -TimeoutSec 5; if ($response.StatusCode -eq 200) { Write-Host '[OK] Dashboard accessible' -ForegroundColor Green; exit 0 } else { Write-Host '[ERROR] Dashboard returned status' $response.StatusCode -ForegroundColor Red; exit 1 } } catch { Write-Host '[ERROR] Cannot connect to dashboard' -ForegroundColor Red; Write-Host 'Make sure dashboard is running on rover' -ForegroundColor Yellow; exit 1 }"

if %errorLevel% equ 0 (
    echo.
    echo [3/3] Opening dashboard...
    echo.
    echo ============================================================
    echo SUCCESS! DASHBOARD ACCESSIBLE VIA ZEROTIER
    echo ============================================================
    echo.
    echo Rover IP: 172.25.133.85
    echo Dashboard URL: http://172.25.133.85:8081
    echo.
    echo Opening dashboard in your browser...
    start http://172.25.133.85:8081
    echo.
    echo [SUCCESS] Dashboard opened!
) else (
    echo.
    echo ============================================================
    echo DASHBOARD NOT ACCESSIBLE
    echo ============================================================
    echo.
    echo Please check on the rover (Ubuntu):
    echo 1. Start services: python3 rover_manager_v7.py
    echo 2. Open firewall: sudo ufw allow 8081
    echo 3. Test local: curl http://localhost:8081
    echo.
)

echo.
pause
