@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app\delivery_console.py
) else (
  python app\delivery_console.py
)
if errorlevel 1 pause
