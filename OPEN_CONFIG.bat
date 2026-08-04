@echo off
setlocal
cd /d "%~dp0"

echo Oeffne Konfigurationsdatei...
if not exist "%~dp0config\config.json" (
    echo config\config.json nicht gefunden.
    pause
    exit /b 1
)
notepad "%~dp0config\config.json"
