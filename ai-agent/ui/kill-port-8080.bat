@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Kill all processes using port 8080
echo ========================================

set FOUND=0

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080 ^| findstr LISTENING') do (
    set FOUND=1
    echo Killing PID %%a ...
    taskkill /F /PID %%a
)

if "%FOUND%"=="0" (
    echo No process is listening on port 8080.
)

echo.
echo Done.
pause
