# Project Astra NZ - Dashboard Setup V4
# Windows EC2 Setup Script for AWS Dashboard Receiver

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "     PROJECT ASTRA NZ - DASHBOARD SETUP V4" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Configuration
$DASHBOARD_DIR = "C:\MissionControlServer"
$PYTHON_VERSION = "3.10"
$ZEROTIER_NETWORK = "41d49af6c276269e"
$DASHBOARD_PORT = 8081
$CONFIG_FILE = "$DASHBOARD_DIR\dashboard_config.json"

# Function to check if running as administrator
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to test command existence
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Step 1: Check Administrator
Write-Host "`n[1/8] Administrator Check" -ForegroundColor Yellow
Write-Host ("-" * 40)
if (Test-Administrator) {
    Write-Host "✓ Running as Administrator" -ForegroundColor Green
} else {
    Write-Host "⚠ Not running as Administrator" -ForegroundColor Yellow
    Write-Host "Some features may not work. Run PowerShell as Administrator for full setup" -ForegroundColor Yellow
}

# Step 2: Create directories
Write-Host "`n[2/8] Directory Structure" -ForegroundColor Yellow
Write-Host ("-" * 40)

$directories = @(
    $DASHBOARD_DIR,
    "$DASHBOARD_DIR\images",
    "$DASHBOARD_DIR\data",
    "$DASHBOARD_DIR\logs",
    "$DASHBOARD_DIR\backup"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✓ Created $dir" -ForegroundColor Green
    } else {
        Write-Host "✓ Directory exists: $dir" -ForegroundColor Green
    }
}

# Step 3: Check Python
Write-Host "`n[3/8] Python Installation" -ForegroundColor Yellow
Write-Host ("-" * 40)

if (Test-Command python) {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
    
    # Install required packages
    Write-Host "Installing Python packages..." -ForegroundColor Cyan
    
    $packages = @(
        "flask",
        "requests", 
        "pillow",
        "pywin32"
    )
    
    foreach ($package in $packages) {
        Write-Host "  Installing $package..." -NoNewline
        $result = pip install $package 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✓" -ForegroundColor Green
        } else {
            Write-Host " ✗" -ForegroundColor Red
        }
    }
} else {
    Write-Host "✗ Python not found" -ForegroundColor Red
    Write-Host "Please install Python $PYTHON_VERSION from https://www.python.org/downloads/" -ForegroundColor Yellow
    
    $install = Read-Host "Open Python download page? (Y/N)"
    if ($install -eq "Y") {
        Start-Process "https://www.python.org/downloads/"
    }
}

# Step 4: Check ZeroTier
Write-Host "`n[4/8] ZeroTier Network" -ForegroundColor Yellow
Write-Host ("-" * 40)

$zerotierPath = "C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat"
if (Test-Path $zerotierPath) {
    Write-Host "✓ ZeroTier installed" -ForegroundColor Green
    
    # Check status
    $status = & $zerotierPath status 2>&1
    if ($status -match "ONLINE") {
        Write-Host "✓ ZeroTier online" -ForegroundColor Green
        
        # Check network membership
        $networks = & $zerotierPath listnetworks 2>&1
        if ($networks -match $ZEROTIER_NETWORK) {
            Write-Host "✓ Connected to UGV Network" -ForegroundColor Green
        } else {
            Write-Host "⚠ Not connected to UGV Network" -ForegroundColor Yellow
            $join = Read-Host "Join network $ZEROTIER_NETWORK? (Y/N)"
            if ($join -eq "Y") {
                & $zerotierPath join $ZEROTIER_NETWORK
                Write-Host "✓ Network join requested" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "⚠ ZeroTier not running" -ForegroundColor Yellow
        Write-Host "Start ZeroTier service from system tray or services" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ ZeroTier not installed" -ForegroundColor Red
    Write-Host "Download from: https://www.zerotier.com/download/" -ForegroundColor Yellow
    
    $install = Read-Host "Open ZeroTier download page? (Y/N)"
    if ($install -eq "Y") {
        Start-Process "https://www.zerotier.com/download/"
    }
}

# Step 5: Configure Firewall
Write-Host "`n[5/8] Firewall Configuration" -ForegroundColor Yellow
Write-Host ("-" * 40)

if (Test-Administrator) {
    # Add firewall rules for dashboard
    $ruleName = "Project Astra Dashboard"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    
    if (!$existingRule) {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort $DASHBOARD_PORT `
            -Action Allow `
            -Profile Any | Out-Null
        Write-Host "✓ Firewall rule created for port $DASHBOARD_PORT" -ForegroundColor Green
    } else {
        Write-Host "✓ Firewall rule exists for port $DASHBOARD_PORT" -ForegroundColor Green
    }
    
    # Additional ports
    $additionalPorts = @(8080, 5000)
    foreach ($port in $additionalPorts) {
        $ruleName = "Project Astra Port $port"
        $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        
        if (!$existingRule) {
            New-NetFirewallRule -DisplayName $ruleName `
                -Direction Inbound `
                -Protocol TCP `
                -LocalPort $port `
                -Action Allow `
                -Profile Any | Out-Null
            Write-Host "✓ Firewall rule created for port $port" -ForegroundColor Green
        }
    }
} else {
    Write-Host "⚠ Cannot configure firewall without Administrator rights" -ForegroundColor Yellow
    Write-Host "Run as Administrator to configure firewall" -ForegroundColor Yellow
}

# Step 6: Check Port Availability
Write-Host "`n[6/8] Port Availability" -ForegroundColor Yellow
Write-Host ("-" * 40)

$ports = @{
    8080 = "Main Dashboard"
    8081 = "Receiver Service"
    5000 = "Web Interface"
}

foreach ($port in $ports.Keys) {
    $tcpConnection = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
    
    if ($tcpConnection.TcpTestSucceeded) {
        Write-Host "⚠ Port $port ($($ports[$port])) is in use" -ForegroundColor Yellow
    } else {
        Write-Host "✓ Port $port ($($ports[$port])) is available" -ForegroundColor Green
    }
}

# Step 7: Create Configuration
Write-Host "`n[7/8] Configuration File" -ForegroundColor Yellow
Write-Host ("-" * 40)

# Get local IP address
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch "Loopback"}).IPAddress[0]

$config = @{
    dashboard_ip = $localIP
    dashboard_port = $DASHBOARD_PORT
    zerotier_network = $ZEROTIER_NETWORK
    image_dir = "$DASHBOARD_DIR\images"
    data_dir = "$DASHBOARD_DIR\data"
    log_dir = "$DASHBOARD_DIR\logs"
    max_images = 1000
    retention_days = 30
}

$config | ConvertTo-Json | Out-File -FilePath $CONFIG_FILE -Encoding UTF8
Write-Host "✓ Configuration saved to $CONFIG_FILE" -ForegroundColor Green
Write-Host "  Dashboard IP: $localIP" -ForegroundColor Cyan
Write-Host "  Dashboard Port: $DASHBOARD_PORT" -ForegroundColor Cyan

# Step 8: Create Startup Script
Write-Host "`n[8/8] Startup Configuration" -ForegroundColor Yellow
Write-Host ("-" * 40)

$startupScript = @"
@echo off
echo ============================================================
echo     PROJECT ASTRA NZ - DASHBOARD RECEIVER
echo ============================================================
echo.
cd /d $DASHBOARD_DIR
echo Starting dashboard receiver on port $DASHBOARD_PORT...
python dashboard_receiver_v4.py
pause
"@

$startupScript | Out-File -FilePath "$DASHBOARD_DIR\start_dashboard.bat" -Encoding ASCII
Write-Host "✓ Startup script created: start_dashboard.bat" -ForegroundColor Green

# Create PowerShell startup script
$psStartupScript = @'
# Project Astra Dashboard Startup
$Host.UI.RawUI.WindowTitle = "Project Astra Dashboard"
Set-Location $DASHBOARD_DIR

Write-Host "Starting Project Astra Dashboard..." -ForegroundColor Cyan
python dashboard_receiver_v4.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard failed to start. Check logs." -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
'@

$psStartupScript | Out-File -FilePath "$DASHBOARD_DIR\Start-Dashboard.ps1" -Encoding UTF8
Write-Host "✓ PowerShell startup script created: Start-Dashboard.ps1" -ForegroundColor Green

# Create scheduled task for auto-start
$createTask = Read-Host "`nCreate Windows scheduled task for auto-start? (Y/N)"
if ($createTask -eq "Y" -and (Test-Administrator)) {
    $taskName = "ProjectAstraDashboard"
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($existingTask) {
        Write-Host "⚠ Scheduled task already exists" -ForegroundColor Yellow
    } else {
        $action = New-ScheduledTaskAction -Execute "python.exe" -Argument "$DASHBOARD_DIR\dashboard_receiver_v4.py" -WorkingDirectory $DASHBOARD_DIR
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType ServiceAccount -RunLevel Highest
        
        Register-ScheduledTask -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description "Project Astra NZ Dashboard Receiver Service" | Out-Null
            
        Write-Host "✓ Scheduled task created for auto-start" -ForegroundColor Green
    }
}

# Summary
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "                    SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nConfiguration Summary:" -ForegroundColor Yellow
Write-Host "  Dashboard Directory: $DASHBOARD_DIR" -ForegroundColor White
Write-Host "  Dashboard IP: $localIP" -ForegroundColor White
Write-Host "  Dashboard Port: $DASHBOARD_PORT" -ForegroundColor White
Write-Host "  ZeroTier Network: $ZEROTIER_NETWORK" -ForegroundColor White

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Copy dashboard_receiver_v4.py to $DASHBOARD_DIR" -ForegroundColor White
Write-Host "2. Start dashboard: Run start_dashboard.bat" -ForegroundColor White
Write-Host "3. Access status page: http://localhost:$DASHBOARD_PORT" -ForegroundColor White
Write-Host "4. Verify rover connection via ZeroTier" -ForegroundColor White

Write-Host "`n✅ Setup complete!" -ForegroundColor Green

# Keep window open
Read-Host "`nPress Enter to exit"
