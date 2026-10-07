@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Esegui prima Installa_Windows.bat & pause & exit /b 1)
set RADICE=%USERPROFILE%\Riservato_AnalisiCrisi\CASI
if not exist "%RADICE%" mkdir "%RADICE%"
echo Apri http://127.0.0.1:8765 - per fermare: chiudi questa finestra, Ctrl+C oppure Arresta_Windows.bat
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe interfaccia_locale.py --radice "%RADICE%"
