@echo off
setlocal
cd /d "%~dp0\Server Performance Monitoring Project"

set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PYTHON%" (
    set "PYTHON=python"
)

echo ======================================================================
echo Dang khoi dong toan bo he thong: Web Dashboard + Tkinter + Socket Server
echo ======================================================================
"%PYTHON%" run_system.py all

if errorlevel 1 pause
endlocal
