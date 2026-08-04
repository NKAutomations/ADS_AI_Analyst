@echo off
setlocal

REM === Immer in den Ordner wechseln, in dem diese .bat-Datei liegt ===
cd /d "%~dp0"
echo Arbeitsverzeichnis: %CD%
echo.

echo ============================================================
echo  ADS_KI_Analyse - Installation
echo ============================================================
echo.

REM Altes fehlerhaftes .venv in System32 aufraumen (falls vorhanden)
if exist "C:\Windows\System32\.venv" (
    echo HINWEIS: Fehlerhaftes .venv in System32 gefunden - wird geloescht...
    rmdir /s /q "C:\Windows\System32\.venv"
    echo Bereinigt.
    echo.
)

REM Lokales .venv im Projektordner loeschen falls es leer/kaputt ist
if exist ".venv" (
    if not exist ".venv\Scripts\python.exe" (
        echo Unvollstaendiges .venv gefunden - wird neu erstellt...
        rmdir /s /q ".venv"
    ) else (
        echo Virtuelle Umgebung bereits vorhanden.
    )
)

set PYTHON_EXE=
for %%v in (3.13 3.12 3.11) do (
    if not defined PYTHON_EXE (
        py -%%v --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON_EXE=py -%%v
            echo Python %%v gefunden.
        )
    )
)

if not defined PYTHON_EXE (
    echo FEHLER: Python 3.11, 3.12 oder 3.13 nicht gefunden.
    echo Bitte Python von https://www.python.org/downloads/ installieren.
    pause
    exit /b 1
)

echo Verwende: %PYTHON_EXE%
echo.

if not exist ".venv" (
    echo Erstelle virtuelle Umgebung in: %CD%\.venv
    %PYTHON_EXE% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo FEHLER beim Erstellen der virtuellen Umgebung.
        pause
        exit /b 1
    )
    echo Virtuelle Umgebung erstellt.
)

echo.
echo Pruefe .venv...
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo FEHLER: .venv\Scripts\python.exe nicht gefunden.
    echo Bitte Administratorrechte pruefen oder Ordner manuell loeschen und neu starten.
    pause
    exit /b 1
)

echo .venv OK: %~dp0.venv\Scripts\python.exe
echo.

echo Aktualisiere pip...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip

echo.
echo Installiere Abhaengigkeiten...
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo FEHLER: Paketinstallation fehlgeschlagen.
    echo.
    echo Tipp: Falls interne pip-Quelle PySide6 nicht bereitstellt,
    echo       fuehren Sie manuell aus:
    echo.
    echo   "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" --index-url https://pypi.org/simple/
    echo.
    pause
    exit /b 1
)

echo.
echo Pruefe Installation...
"%~dp0.venv\Scripts\python.exe" -c "import PySide6, httpx, pydantic; from app.ads.ads_client import _import_pyads; _import_pyads(); print('OK - Alle Pakete verfuegbar')"

if errorlevel 1 (
    echo WARNUNG: Nicht alle Pakete importierbar. Bitte Fehler pruefen.
) else (
    echo.
    echo ============================================================
    echo  Installation erfolgreich!
    echo  Starten Sie die Anwendung mit: START_ADS.bat
    echo ============================================================
)
echo.
pause
