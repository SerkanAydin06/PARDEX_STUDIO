@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 app\worker_console.py
if errorlevel 1 pause
