@echo off
setlocal
if not exist "%ProgramFiles%\Rhino 8\System\Yak.exe" (
 echo Rhino 8 was not found in Program Files. See Help\BETA_QUICK_START.md.
 pause
 exit /b 2
)
tasklist /FI "IMAGENAME eq Rhino.exe" /NH 2>nul | findstr /I /C:"Rhino.exe" >nul
if not errorlevel 1 (
 echo Save your drawings and close ALL Rhino windows, then run this helper again.
 pause
 exit /b 3
)
"%ProgramFiles%\Rhino 8\System\Yak.exe" install "%~dp0rhino-urbanism-toolkit-0.1.0-beta1+20601-rh8_36-win.yak"
if errorlevel 1 (
 echo The operation did not complete. Keep the message above and contact Rune.
 pause
 exit /b 1
)
echo Done. See Help\BETA_QUICK_START.md for the next step.
pause
exit /b 0
