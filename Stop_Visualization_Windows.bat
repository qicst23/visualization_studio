@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Stopping any running OptimusKG Visualization Studio server on 127.0.0.1:8004..8010...
powershell -NoProfile -ExecutionPolicy Bypass -Command "8004..8010 | ForEach-Object { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 -Uri ('http://127.0.0.1:' + $_ + '/api/shutdown') | Out-Null; Write-Host ('Stopped server on port ' + $_) } catch {} }"
timeout /t 2 >nul
endlocal
