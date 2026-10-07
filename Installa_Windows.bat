@echo off
rem Installa ANALISI CRISI (copia GMKtec) su Windows NATIVO: .venv locale, dipendenze, prove. Rilanciabile. NON PROVATO su Windows: se fallisce, usa WSL (Installa_Linux.sh).
cd /d "%~dp0"
echo === ANALISI CRISI (GMKtec) - installazione Windows ===
set PYC=
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  if not defined PYC (py -%%V -c "import sys" >nul 2>&1 && set PYC=py -%%V)
)
if not defined PYC (
  echo ERRORE: serve Python 3.10 o superiore con il launcher "py" ^(https://www.python.org/downloads/windows/^).
  pause & exit /b 1
)
echo Uso: %PYC%
.venv\Scripts\python.exe -c "import reportlab, pdfplumber, PIL" >nul 2>&1
if errorlevel 1 (
  echo Creo l'ambiente locale .venv...
  if exist .venv rmdir /s /q .venv
  %PYC% -m venv .venv || (echo ERRORE: creazione .venv & pause & exit /b 1)
  .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt || (echo ERRORE: dipendenze & pause & exit /b 1)
)
set KO=0
for %%T in (test_pratica test_correzioni_rev3 test_percorso_interfaccia test_llm_locale) do (
  .venv\Scripts\python.exe test_sintetici\%%T.py > "%TEMP%\analisi_crisi_%%T.log" 2>&1
  if errorlevel 1 (echo Prova %%T: FALLITA - vedi %TEMP%\analisi_crisi_%%T.log & set KO=1) else (echo Prova %%T: OK)
)
if not exist "%USERPROFILE%\Riservato_AnalisiCrisi\CASI" mkdir "%USERPROFILE%\Riservato_AnalisiCrisi\CASI"
echo OCR locale: tesseract e pdftoppm devono essere nel PATH ^(facoltativo, solo per PDF scansionati^).
if "%KO%"=="0" (echo === INSTALLAZIONE COMPLETATA ===) else (echo === INSTALLAZIONE CON ERRORI: non usare l'app ===)
pause
