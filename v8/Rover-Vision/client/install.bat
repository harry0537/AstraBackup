@echo off
REM Rover-Vision Client Installer
REM Professional installation script for Windows EC2 systems

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Configuration
set "INSTALL_DIR=%PROGRAMFILES%\Rover-Vision"
set "APP_DATA=%APPDATA%\Rover-Vision"
set "SERVICE_NAME=RoverVisionClient"

REM Print colored output
:print_status
echo %BLUE%[INFO]%NC% %~1
goto :eof

:print_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:print_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:print_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM Check if running as administrator
:check_admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    call :print_error "This script must be run as administrator"
    pause
    exit /b 1
)
call :print_success "Running as administrator"

REM Check system requirements
:check_requirements
call :print_status "Checking system requirements..."

REM Check Windows version
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
if %VERSION% LSS 10.0 (
    call :print_warning "Windows 10+ recommended. Found: %VERSION%"
)

REM Check .NET Framework
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full\" /v Release >nul 2>&1
if %errorLevel% neq 0 (
    call :print_error ".NET Framework 4.7.2+ is required"
    pause
    exit /b 1
)

REM Check ZeroTier
where zerotier-cli >nul 2>&1
if %errorLevel% neq 0 (
    call :print_warning "ZeroTier client not found. Please install ZeroTier first."
    call :print_status "Download from: https://www.zerotier.com/download/"
    pause
)

call :print_success "System requirements met"

REM Create installation directories
:setup_directories
call :print_status "Creating installation directories..."

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%APP_DATA%" mkdir "%APP_DATA%"
if not exist "%APP_DATA%\config" mkdir "%APP_DATA%\config"
if not exist "%APP_DATA%\logs" mkdir "%APP_DATA%\logs"

call :print_success "Installation directories created"

REM Copy application files
:install_files
call :print_status "Installing application files..."

copy "rover-vision-client.exe" "%INSTALL_DIR%\" >nul
copy "config\default.json" "%APP_DATA%\config\" >nul

call :print_success "Application files installed"

REM Create configuration file
:create_config
call :print_status "Creating configuration file..."

echo {> "%APP_DATA%\config\config.json"
echo   "server": {>> "%APP_DATA%\config\config.json"
echo     "ip": "ROVER_ZEROTIER_IP",>> "%APP_DATA%\config\config.json"
echo     "port": 8081,>> "%APP_DATA%\config\config.json"
echo     "timeout": 30>> "%APP_DATA%\config\config.json"
echo   },>> "%APP_DATA%\config\config.json"
echo   "network": {>> "%APP_DATA%\config\config.json"
echo     "zerotier_enabled": true,>> "%APP_DATA%\config\config.json"
echo     "auto_reconnect": true,>> "%APP_DATA%\config\config.json"
echo     "reconnect_interval": 5>> "%APP_DATA%\config\config.json"
echo   },>> "%APP_DATA%\config\config.json"
echo   "dashboard": {>> "%APP_DATA%\config\config.json"
echo     "auto_refresh": true,>> "%APP_DATA%\config\config.json"
echo     "refresh_interval": 1000,>> "%APP_DATA%\config\config.json"
echo     "fullscreen": false>> "%APP_DATA%\config\config.json"
echo   }>> "%APP_DATA%\config\config.json"
echo }>> "%APP_DATA%\config\config.json"

call :print_success "Configuration file created"

REM Create desktop shortcut
:create_shortcut
call :print_status "Creating desktop shortcut..."

set "DESKTOP=%USERPROFILE%\Desktop"
echo [InternetShortcut] > "%DESKTOP%\Rover-Vision Client.url"
echo URL=file:///%INSTALL_DIR%/rover-vision-client.exe >> "%DESKTOP%\Rover-Vision Client.url"
echo IconFile=%INSTALL_DIR%/rover-vision-client.exe >> "%DESKTOP%\Rover-Vision Client.url"
echo IconIndex=0 >> "%DESKTOP%\Rover-Vision Client.url"

call :print_success "Desktop shortcut created"

REM Create start menu shortcut
:create_start_menu
call :print_status "Creating start menu shortcut..."

set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
if not exist "%START_MENU%\Rover-Vision" mkdir "%START_MENU%\Rover-Vision"

echo [InternetShortcut] > "%START_MENU%\Rover-Vision\Rover-Vision Client.url"
echo URL=file:///%INSTALL_DIR%/rover-vision-client.exe >> "%START_MENU%\Rover-Vision\Rover-Vision Client.url"
echo IconFile=%INSTALL_DIR%/rover-vision-client.exe >> "%START_MENU%\Rover-Vision\Rover-Vision Client.url"
echo IconIndex=0 >> "%START_MENU%\Rover-Vision\Rover-Vision Client.url"

call :print_success "Start menu shortcut created"

REM Create uninstaller
:create_uninstaller
call :print_status "Creating uninstaller..."

echo @echo off > "%INSTALL_DIR%\uninstall.bat"
echo REM Rover-Vision Client Uninstaller >> "%INSTALL_DIR%\uninstall.bat"
echo echo Uninstalling Rover-Vision Client... >> "%INSTALL_DIR%\uninstall.bat"
echo taskkill /f /im rover-vision-client.exe ^>nul 2^>^&1 >> "%INSTALL_DIR%\uninstall.bat"
echo del "%INSTALL_DIR%\rover-vision-client.exe" >> "%INSTALL_DIR%\uninstall.bat"
echo rmdir /s /q "%INSTALL_DIR%" >> "%INSTALL_DIR%\uninstall.bat"
echo rmdir /s /q "%APP_DATA%" >> "%INSTALL_DIR%\uninstall.bat"
echo del "%DESKTOP%\Rover-Vision Client.url" >> "%INSTALL_DIR%\uninstall.bat"
echo rmdir /s /q "%START_MENU%\Rover-Vision" >> "%INSTALL_DIR%\uninstall.bat"
echo echo Rover-Vision Client uninstalled successfully. >> "%INSTALL_DIR%\uninstall.bat"
echo pause >> "%INSTALL_DIR%\uninstall.bat"

call :print_success "Uninstaller created"

REM Create control script
:create_control_script
call :print_status "Creating control script..."

echo @echo off > "%INSTALL_DIR%\rover-vision-client.bat"
echo REM Rover-Vision Client Control Script >> "%INSTALL_DIR%\rover-vision-client.bat"
echo set "INSTALL_DIR=%INSTALL_DIR%" >> "%INSTALL_DIR%\rover-vision-client.bat"
echo set "APP_DATA=%APP_DATA%" >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="start" goto start >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="stop" goto stop >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="restart" goto restart >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="status" goto status >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="config" goto config >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if "%%1"=="test" goto test >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto help >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :start >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Starting Rover-Vision Client... >> "%INSTALL_DIR%\rover-vision-client.bat"
echo start "" "%INSTALL_DIR%\rover-vision-client.exe" >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :stop >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Stopping Rover-Vision Client... >> "%INSTALL_DIR%\rover-vision-client.bat"
echo taskkill /f /im rover-vision-client.exe >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :restart >> "%INSTALL_DIR%\rover-vision-client.bat"
echo call :stop >> "%INSTALL_DIR%\rover-vision-client.bat"
echo timeout /t 2 /nobreak ^>nul >> "%INSTALL_DIR%\rover-vision-client.bat"
echo call :start >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :status >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Rover-Vision Client Status: >> "%INSTALL_DIR%\rover-vision-client.bat"
echo tasklist /fi "imagename eq rover-vision-client.exe" ^| find "rover-vision-client.exe" ^>nul >> "%INSTALL_DIR%\rover-vision-client.bat"
echo if %%errorlevel%% equ 0 ( >> "%INSTALL_DIR%\rover-vision-client.bat"
echo   echo   Status: RUNNING >> "%INSTALL_DIR%\rover-vision-client.bat"
echo ^) else ( >> "%INSTALL_DIR%\rover-vision-client.bat"
echo   echo   Status: STOPPED >> "%INSTALL_DIR%\rover-vision-client.bat"
echo ^) >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :config >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Opening configuration... >> "%INSTALL_DIR%\rover-vision-client.bat"
echo notepad "%APP_DATA%\config\config.json" >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :test >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Testing connection... >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Please configure the rover IP address in the config file first. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo goto end >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :help >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Rover-Vision Client Control >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo ========================== >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Usage: rover-vision-client {start^|stop^|restart^|status^|config^|test} >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo Commands: >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   start     - Start the client >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   stop      - Stop the client >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   restart   - Restart the client >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   status    - Show client status >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   config    - Edit configuration >> "%INSTALL_DIR%\rover-vision-client.bat"
echo echo   test      - Test connection >> "%INSTALL_DIR%\rover-vision-client.bat"
echo. >> "%INSTALL_DIR%\rover-vision-client.bat"
echo :end >> "%INSTALL_DIR%\rover-vision-client.bat"

call :print_success "Control script created"

REM Add to PATH
:add_to_path
call :print_status "Adding to PATH..."

setx PATH "%PATH%;%INSTALL_DIR%" /M >nul 2>&1
if %errorLevel% neq 0 (
    call :print_warning "Could not add to system PATH. You may need to restart your command prompt."
) else (
    call :print_success "Added to PATH"
)

REM Main installation function
:main
echo.
echo ==========================================
echo Rover-Vision Client Installer
echo ==========================================
echo.

call :check_admin
call :check_requirements
call :setup_directories
call :install_files
call :create_config
call :create_shortcut
call :create_start_menu
call :create_uninstaller
call :create_control_script
call :add_to_path

echo.
call :print_success "Rover-Vision Client installed successfully!"
echo.
echo Next steps:
echo 1. Configure ZeroTier network
echo 2. Update rover IP in config: %APP_DATA%\config\config.json
echo 3. Start client: rover-vision-client start
echo 4. Test connection: rover-vision-client test
echo.
echo Configuration file: %APP_DATA%\config\config.json
echo Logs: %APP_DATA%\logs\
echo.

pause
goto :eof
