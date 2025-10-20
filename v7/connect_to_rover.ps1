# Project Astra NZ - Rover Connection Script (PowerShell)
# Run as Administrator

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PROJECT ASTRA NZ - ROVER CONNECTION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if ZeroTier is running
$zerotierProcess = Get-Process -Name "zerotier-one" -ErrorAction SilentlyContinue
if ($zerotierProcess) {
    Write-Host "[OK] ZeroTier is running" -ForegroundColor Green
} else {
    Write-Host "[ERROR] ZeroTier is not running" -ForegroundColor Red
    Write-Host "Please run setup_zerotier_windows.bat first" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[1/3] Checking ZeroTier network status..." -ForegroundColor Yellow
& "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat" listnetworks

Write-Host ""
Write-Host "[2/3] Testing rover connectivity..." -ForegroundColor Yellow
$roverIP = "172.25.133.85"
$pingResult = Test-Connection -ComputerName $roverIP -Count 1 -Quiet

if ($pingResult) {
    Write-Host "[OK] Rover is reachable at $roverIP" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Rover not reachable - checking network status..." -ForegroundColor Yellow
    Write-Host "Please ensure:" -ForegroundColor Yellow
    Write-Host "1. ZeroTier network is authorized" -ForegroundColor Yellow
    Write-Host "2. Rover is running and connected" -ForegroundColor Yellow
    Write-Host "3. Network ID: 4753cf475f287023" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[3/3] Starting dashboard connection..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ROVER DASHBOARD ACCESS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Rover IP: $roverIP" -ForegroundColor White
Write-Host "Dashboard URL: http://$roverIP`:8081" -ForegroundColor White
Write-Host ""
Write-Host "Opening dashboard in your default browser..." -ForegroundColor Yellow
Write-Host ""

# Open dashboard in default browser
Start-Process "http://$roverIP`:8081"

Write-Host ""
Write-Host "Dashboard opened! If it doesn't load:" -ForegroundColor Yellow
Write-Host "1. Check if rover is running: python3 rover_manager_v7.py" -ForegroundColor Yellow
Write-Host "2. Check if dashboard is running: python3 telemetry_dashboard_v7.py" -ForegroundColor Yellow
Write-Host "3. Verify ZeroTier network authorization" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"
