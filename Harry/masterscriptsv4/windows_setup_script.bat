@echo off
REM Project Astra NZ - Dashboard Server Setup Script
REM Automated installation for Windows EC2 server

echo ==========================================
echo Project Astra NZ Dashboard Server Setup
echo ==========================================
echo.

REM Create project directory
echo Creating project directory...
if not exist "C:\ProjectAstra" mkdir "C:\ProjectAstra"
cd /d "C:\ProjectAstra"

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found: 
python --version

REM Check pip
echo Checking pip...
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not found
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

REM Install required packages
echo.
echo Installing required Python packages...
echo - fastapi: Web framework for dashboard
echo - uvicorn: ASGI server for FastAPI
echo - pydantic: Data validation
echo - websockets: Real-time communication
echo.

pip install fastapi uvicorn pydantic websockets

if errorlevel 1 (
    echo ERROR: Failed to install Python packages
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

REM Configure Windows Firewall
echo.
echo Configuring Windows Firewall for port 8080...

netsh advfirewall firewall add rule name="Project Astra Dashboard" dir=in action=allow protocol=TCP localport=8080 >nul 2>&1

if errorlevel 1 (
    echo WARNING: Failed to configure firewall automatically
    echo You may need to manually allow port 8080 in Windows Firewall
    echo Or run this script as Administrator
) else (
    echo Firewall rule added successfully
)

REM Create run script
echo.
echo Creating run script...

echo @echo off > run_dashboard.bat
echo cd /d "C:\ProjectAstra" >> run_dashboard.bat
echo echo Starting Project Astra Dashboard Server... >> run_dashboard.bat
echo echo Dashboard will be available at: http://10.244.77.186:8080 >> run_dashboard.bat
echo echo Press Ctrl+C to stop >> run_dashboard.bat
echo python dashboard_server_v1.py >> run_dashboard.bat

REM Create test script
echo.
echo Creating test connectivity script...

echo @echo off > test_connectivity.bat
echo echo Testing ZeroTier connectivity... >> test_connectivity.bat
echo ping -n 4 10.244.77.186 >> test_connectivity.bat
echo echo. >> test_connectivity.bat
echo echo Testing if dashboard port is accessible... >> test_connectivity.bat
echo netstat -an ^| findstr :8080 >> test_connectivity.bat
echo echo. >> test_connectivity.bat
echo echo If you see "0.0.0.0:8080" or ":::8080" above, the server is running >> test_connectivity.bat
echo pause >> test_connectivity.bat

REM Summary
echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Installation Directory: C:\ProjectAstra
echo.
echo Next Steps:
echo 1. Copy dashboard_server_v1.py to this directory
echo 2. Run: run_dashboard.bat
echo 3. Access dashboard: http://10.244.77.186:8080
echo.
echo Useful Commands:
echo - Start Dashboard: run_dashboard.bat  
echo - Test Network: test_connectivity.bat
echo - Check Status: netstat -an ^| findstr :8080
echo.
echo ZeroTier Network Configuration:
echo - Server IP: 10.244.77.186
echo - Dashboard Port: 8080
echo - Rover should connect to: http://10.244.77.186:8080
echo.

REM Check ZeroTier
echo Checking ZeroTier network connectivity...
ping -n 2 10.244.77.186 >nul 2>&1
if errorlevel 1 (
    echo WARNING: ZeroTier network issue detected
    echo Please check: zerotier-cli status
) else (
    echo ✓ ZeroTier network connectivity confirmed: 10.244.77.186
)

echo.
echo Setup script completed successfully!
echo You can now run the dashboard server.
echo.
pause
