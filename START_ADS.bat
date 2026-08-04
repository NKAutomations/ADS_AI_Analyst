@echo off
setlocal
cd /d "%~dp0"

echo Starte ADS_KI_Analyse...
echo Verzeichnis: %CD%
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo FEHLER: Virtuelle Umgebung nicht gefunden.
    echo Bitte zuerst INSTALL.bat ausfuehren.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" "%~dp0app\main.py"

if errorlevel 1 (
    echo.
    echo Anwendung mit Fehler beendet.
    pause
)
