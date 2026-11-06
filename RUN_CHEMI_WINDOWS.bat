@echo off
setlocal
cd /d "%~dp0"
echo [CHEMI] Checking Python 3...
set "PYTHON_CMD="
py -3 -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python -c "import sys; assert sys.version_info.major == 3" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo.
    echo [ERROR] Python 3 was not found.
    echo Install Python 3 from https://www.python.org/downloads/
    echo During setup, enable Add python.exe to PATH.
    pause
    exit /b 1
)
echo [CHEMI] Starting server at http://127.0.0.1:8000
%PYTHON_CMD% server.py
if errorlevel 1 (
    echo.
    echo [ERROR] Server stopped due to an error. Check the message above.
)
pause
endlocal
