@echo off
REM Quick start script for Bot MVP (Windows batch file)
REM This script will start both API and Web servers in separate windows

echo.
echo ====================================================
echo   Bot MVP - Quick Start
echo ====================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo Error: .env file not found!
    echo Please create .env file with ANTHROPIC_API_KEY and other settings
    pause
    exit /b 1
)

REM Install requirements if needed
echo Checking dependencies...
pip list | findstr -i fastapi >nul
if %errorlevel% neq 0 (
    echo Installing required packages...
    pip install -r requirements.txt
)

REM Kill existing processes on ports 8100 and 8080 if they exist
echo Cleaning up old processes...
netstat -ano | findstr :8100 >nul 2>&1
if %errorlevel% equ 0 (
    echo Closing existing API server (port 8100)...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8100') do taskkill /PID %%a /F 2>nul
    timeout /t 1 /nobreak >nul
)

netstat -ano | findstr :8080 >nul 2>&1
if %errorlevel% equ 0 (
    echo Closing existing Web server (port 8080)...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080') do taskkill /PID %%a /F 2>nul
    timeout /t 1 /nobreak >nul
)

REM Start API server in new window
echo.
echo Starting API Server (port 8100)...
start "Bot MVP - API Server" cmd /k "python api.py"
timeout /t 2 /nobreak >nul

REM Start Web server in new window
echo Starting Web Server (port 8080)...
start "Bot MVP - Web Server" cmd /k "python web_server.py"
timeout /t 2 /nobreak >nul

echo.
echo ====================================================
echo   Servers started successfully!
echo ====================================================
echo.
echo URLs:
echo   Chat:      http://localhost:8080/index.html
echo   API Docs:  http://localhost:8100/docs
echo   Stats:     http://localhost:8080/stats.html
echo   Admin:     http://localhost:8080/admin.html
echo.
echo Logs are displayed in separate windows (you can close them to stop)
echo.
pause
