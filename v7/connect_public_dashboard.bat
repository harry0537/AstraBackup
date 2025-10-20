@echo off
echo ============================================================
echo PROJECT ASTRA NZ - PUBLIC DASHBOARD ACCESS
echo ============================================================
echo.

echo [1/3] Getting server public IP...
echo Please run this on the rover server first:
echo python3 setup_public_dashboard.py
echo.

set /p PUBLIC_IP="Enter the public IP address: "

if "%PUBLIC_IP%"=="" (
    echo [ERROR] No IP address provided
    pause
    exit /b 1
)

echo.
echo [2/3] Testing public dashboard access...
echo Testing http://%PUBLIC_IP%:8081...

powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%PUBLIC_IP%:8081' -TimeoutSec 10; if ($response.StatusCode -eq 200) { Write-Host '[OK] Dashboard accessible' -ForegroundColor Green; exit 0 } else { Write-Host '[ERROR] Dashboard returned status' $response.StatusCode -ForegroundColor Red; exit 1 } } catch { Write-Host '[ERROR] Cannot connect to dashboard' -ForegroundColor Red; Write-Host 'Make sure:' -ForegroundColor Yellow; Write-Host '1. Dashboard is running on server' -ForegroundColor Yellow; Write-Host '2. Port 8081 is open in firewall' -ForegroundColor Yellow; Write-Host '3. Server security groups allow port 8081' -ForegroundColor Yellow; exit 1 }"

if %errorLevel% equ 0 (
    echo.
    echo [3/3] Opening public dashboard...
    echo.
    echo ============================================================
    echo SUCCESS! PUBLIC DASHBOARD ACCESS
    echo ============================================================
    echo.
    echo Public IP: %PUBLIC_IP%
    echo Dashboard URL: http://%PUBLIC_IP%:8081
    echo.
    echo Opening dashboard in your browser...
    start http://%PUBLIC_IP%:8081
    echo.
    echo [SUCCESS] Dashboard opened in your browser!
) else (
    echo.
    echo ============================================================
    echo DASHBOARD NOT ACCESSIBLE
    echo ============================================================
    echo.
    echo Please check on the rover server:
    echo 1. Run: python3 setup_public_dashboard.py
    echo 2. Start dashboard: python3 telemetry_dashboard_v7.py
    echo 3. Open firewall: sudo ufw allow 8081
    echo 4. Check security groups (if using cloud provider)
    echo.
)

echo.
pause
