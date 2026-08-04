@echo off
setlocal
cd /d "%~dp0"

echo Fuehre automatisierte Tests aus...
echo Verzeichnis: %CD%
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo FEHLER: Virtuelle Umgebung nicht gefunden.
    echo Bitte zuerst INSTALL.bat ausfuehren.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" -m pytest "%~dp0tests\test_core.py" -v
pause
