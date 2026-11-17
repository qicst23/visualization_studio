@echo off
setlocal EnableExtensions EnableDelayedExpansion
title OptimusKG - AMG 757 and AMG 691 Visualization Studio

REM Switch into this script's own folder (supports spaces, OneDrive, and secondary drives D:\ etc.)
cd /d "%~dp0"

set "PY_CMD="

REM 1. Prefer a folder-local virtual environment if created via Install_Optional_Live_Engine_Windows.bat
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD="%~dp0.venv\Scripts\python.exe""
)

REM 2. Check standard Windows 11 Python Launcher (py -3)
if not defined PY_CMD (
    py -3 -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)

REM 3. Check PATH python (explicitly testing execution to skip Windows 11 Microsoft Store WindowsApps stub!)
if not defined PY_CMD (
    python -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

REM 4. Check common per-user Windows 11 Python / Miniconda / Anaconda install locations
if not defined PY_CMD (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%USERPROFILE%\miniconda3\python.exe"
        "%USERPROFILE%\anaconda3\python.exe"
    ) do (
        if not defined PY_CMD if exist %%~P (
            "%%~P" -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
            if not errorlevel 1 set "PY_CMD="%%~P""
        )
    )
)

if defined PY_CMD (
    echo [OptimusKG Studio] Starting local Visualization Studio server on 127.0.0.1...
    %PY_CMD% "%~dp0run_visualization_studio.py" --open-browser %*
    if errorlevel 1 (
        echo.
        echo [Notice] Server exited with an error. Opening standalone offline HTML hub instead...
        start "" "%~dp0index.html"
        pause
    )
) else (
    echo ============================================================================
    echo  No Python 3 installation detected on this Windows 11 PC.
    echo  Opening standalone offline Visualization Hub directly in your web browser!
    echo  (AMG 757 Studio, AMG 691 Studio, and Slide Deck work 100%% offline.)
    echo ============================================================================
    start "" "%~dp0index.html"
    timeout /t 4 >nul
)
endlocal
