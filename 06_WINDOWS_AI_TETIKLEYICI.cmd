@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
echo PARDEX 2I - Windows AI Tetikleyici
 echo [1] Ucretsiz zamanlayici onizlemesi
 echo [2] Windows'a SADECE onizleme gorevi kur (5 dakikada bir, 7 gun)
 echo [3] Kurulum durumunu goster
 echo [4] Windows zamanlayici gorevini kaldir
 echo.
 echo AI CALISTIRMA VARSAYILAN OLARAK KAPALIDIR.
set /p CHOICE=Secim (1-4): 
if "%CHOICE%"=="1" %PY% app\windows_trigger_cli.py --preview
if "%CHOICE%"=="2" (
 echo Gorev kurmak icin EVET yazin; bu islem sadece ucretsiz onizleme yapar.
 set /p APPROVE=Onay: 
 call :INSTALL
)
if "%CHOICE%"=="3" %PY% app\windows_trigger_cli.py --status
if "%CHOICE%"=="4" (
 echo Kayitli zamanlayici gorevini kaldirmak icin EVET yazin.
 set /p APPROVE=Onay: 
 call :REMOVE
)
pause
exit /b
:INSTALL
if /I "%APPROVE%"=="EVET" %PY% app\windows_trigger_cli.py --install --confirm
exit /b
:REMOVE
if /I "%APPROVE%"=="EVET" %PY% app\windows_trigger_cli.py --remove --confirm
exit /b
