@echo off
title SEARCH AI
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo   SEARCH AI  -  premium multi-model research generator
echo ============================================================

if not exist "backend\run.py" goto :no_backend
cd /d "%~dp0backend"

rem ---- locate a real Python: prefer the py launcher, skip the Store alias
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto :no_python
for /f "delims=" %%V in ('%PY% --version 2^>^&1') do set "PYVER=%%V"
echo Using %PYVER%

if exist ".venv\Scripts\python.exe" goto :have_venv
echo [1/4] Creating virtual environment...
%PY% -m venv .venv
if errorlevel 1 goto :venv_fail
:have_venv

echo [2/4] Installing dependencies - first run may take a minute...
call ".venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :pip_fail

if exist ".env" goto :have_env
echo [3/4] Creating .env from template...
copy /y ".env.example" ".env" >nul
echo.
echo   IMPORTANT: open  backend\.env  and paste at least ONE
echo   API key AND its model name, for example:
echo       GEMINI_API_KEY=your_key_here
echo       GEMINI_MODEL=your_model_name_here
echo   Then run this launcher again.
echo.
start notepad ".env"
pause
exit /b 0
:have_env
echo [3/4] .env found.

set "PORT=8712"
for /f "tokens=2 delims==" %%P in ('findstr /b /i /c:"APP_PORT=" ".env" 2^>nul') do set "PORT=%%P"
for /f "tokens=2 delims==" %%P in ('findstr /b /i /c:"SEARCH_AI_PORT=" ".env" 2^>nul') do set "PORT=%%P"

echo [3.5/4] Stopping any older SEARCH AI server on port %PORT% ...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":%PORT% " ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>nul
timeout /t 1 /nobreak >nul

echo [4/4] Starting SEARCH AI at http://127.0.0.1:%PORT% ...
set "BOOT=%RANDOM%%RANDOM%%RANDOM%"
start "" "http://127.0.0.1:%PORT%/?boot=%BOOT%"
python run.py

echo.
echo Server stopped. Review any messages above.
pause
exit /b 0

:no_backend
echo.
echo [ERROR] The backend folder was not found next to this launcher.
echo         If you are running this from inside the ZIP file, please
echo         extract everything first: right-click the ZIP, choose
echo         "Extract All", then run START_SEARCH_AI.bat from the
echo         extracted SEARCH_AI folder.
pause
exit /b 1

:no_python
echo.
echo [ERROR] Python 3.10+ was not found on this PC.
echo         Download it from  https://www.python.org/downloads/
echo         and tick "Add python.exe to PATH" during install.
pause
exit /b 1

:venv_fail
echo.
echo [ERROR] Could not create the virtual environment.
echo         If Python came from the Microsoft Store, install the
echo         full version from  https://www.python.org/downloads/
pause
exit /b 1

:pip_fail
echo.
echo [ERROR] Dependency install failed. Common causes: no internet,
echo         or a package has no prebuilt wheel for this Python
echo         version. Scroll up, copy the error text, and share it
echo         to get the exact fix. Then run this launcher again.
pause
exit /b 1
