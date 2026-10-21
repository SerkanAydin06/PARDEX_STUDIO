@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem PARDEX Studio - tek tik kurulum: eksikleri kurar ve sirket panelini acar
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pardex-kur.ps1"
if errorlevel 1 pause
