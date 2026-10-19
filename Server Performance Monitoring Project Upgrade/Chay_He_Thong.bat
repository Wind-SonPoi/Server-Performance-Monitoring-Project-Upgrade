@echo off
setlocal
cd /d "%~dp0\Server Performance Monitoring Project"

set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PYTHON%" (
    set "PYTHON=python"
)

:menu
cls
echo =======================================================================
echo   HE THONG GIAM SAT VA PHAN TICH HIEU NANG MAY CHU PHAN TAN
echo =======================================================================
echo.
echo   [1] Khoi chay TOAN BO (Web Dashboard + Tkinter + Client + Server)
echo   [2] Mo Bang dieu khien Desktop GUI (Tkinter Admin Panel)
echo   [3] Khoi chay Web Dashboard (Flask - http://127.0.0.1:5000)
echo   [4] Chay BO THUC NGHIEM KHOA HOC (Do Latency, SQLite, Anomaly F1)
echo   [5] Chay Client Agent (Thu thap may that)
echo   [0] Thoat
echo.
echo =======================================================================
set /p choice="Nhap lua chon cua ban (0-5): "

if "%choice%"=="1" goto opt1
if "%choice%"=="2" goto opt2
if "%choice%"=="3" goto opt3
if "%choice%"=="4" goto opt4
if "%choice%"=="5" goto opt5
if "%choice%"=="0" goto opt0
goto menu

:opt1
echo.
echo Dang khoi chay toan bo he thong...
"%PYTHON%" run_system.py all
pause
goto menu

:opt2
echo.
echo Dang mo Tkinter Admin Panel...
"%PYTHON%" run_system.py admin
pause
goto menu

:opt3
echo.
echo Dang khoi dong Flask Web Server...
echo Hay mo trinh duyet tai dia chi: http://127.0.0.1:5000
"%PYTHON%" run_system.py web
pause
goto menu

:opt4
echo.
echo Dang chay cac thi nghiem do dac khoa hoc...
"%PYTHON%" run_system.py experiments
pause
goto menu

:opt5
echo.
echo Dang kich hoat Client Agent thu thap may that...
"%PYTHON%" run_system.py client my-pc
pause
goto menu

:opt0
endlocal
exit
