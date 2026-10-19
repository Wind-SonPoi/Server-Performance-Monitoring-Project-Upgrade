@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYTHON%" (
    set "PYTHON=python"
)

if "%~1"=="" goto run_default
"%PYTHON%" run_system.py %*
goto end

:run_default
echo ======================================================================
echo Dang khoi dong toan bo he thong: Web Dashboard + Tkinter + Socket Server
echo ======================================================================
"%PYTHON%" run_system.py all

:end
if errorlevel 1 pause
endlocal
