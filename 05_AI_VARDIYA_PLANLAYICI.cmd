@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "app\schedule_console.py"
  goto end
)
where python >nul 2>&1
if not errorlevel 1 (
  python "app\schedule_console.py"
  goto end
)
echo Python bulunamadi. Once 01_ULTRA_PRO_STUDIO_AC.cmd ile kurulum yapin.
:end
if errorlevel 1 pause
