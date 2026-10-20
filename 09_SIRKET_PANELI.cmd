@echo off
setlocal
cd /d "%~dp0"
rem PARDEX Sirket Merkezi - yerel web paneli (yalnizca bu bilgisayardan erisilir)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app\hq_server.py
) else (
  python app\hq_server.py
)
if errorlevel 1 pause
