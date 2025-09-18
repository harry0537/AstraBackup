@echo off
REM Project Astra NZ - Windows Setup Launcher
REM This script runs the PowerShell setup with proper permissions

echo ============================================================
echo      PROJECT ASTRA NZ - DASHBOARD SETUP LAUNCHER
echo ============================================================
echo.
echo This will setup the AWS EC2 dashboard receiver system.
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running as Administrator
    goto :RunSetup
) else (
    echo [!] Not running as Administrator
    echo.
    echo Requesting Administrator privileges...
    goto :RequestAdmin
)

:RequestAdmin
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:RunSetup
    echo.
    echo Starting PowerShell setup script...
    echo.
    
    REM Run PowerShell setup script with execution policy bypass
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dashboard_setup_v4.ps1"
    
    if %errorLevel% == 0 (
        echo.
        echo Setup completed successfully!
    ) else (
        echo.
        echo Setup encountered errors. Please check the output above.
    )
    
    echo.
    pause
    exit