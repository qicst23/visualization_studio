@echo off
setlocal EnableExtensions
title Install Optional NumPy Live Engine (Windows 11)
cd /d "%~dp0"

set "BASE_PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
if not errorlevel 1 set "BASE_PY=py -3"
if not defined BASE_PY (
    python -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
    if not errorlevel 1 set "BASE_PY=python"
)

if not defined BASE_PY (
    echo [Error] Python 3 is not installed on this Windows 11 PC.
    echo Note: You can still double-click index.html or Launch_Visualization_Windows.bat to use offline browser mode!
    pause
    exit /b 1
)

echo Creating folder-local virtual environment in "%~dp0.venv" ...
%BASE_PY% -m venv "%~dp0.venv"
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements_optional_live_engine.txt"
echo.
echo [Success] Optional Live Neural Engine installed! Double-click Launch_Visualization_Windows.bat to start.
pause
endlocal
