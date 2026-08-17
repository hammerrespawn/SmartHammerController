@echo off
setlocal
cd /d "%~dp0"
title GyroAim agent - Hammer Respawn
set "YOLO_CONFIG_DIR=%CD%\.yolo-config"
set "MPLCONFIGDIR=%CD%\.matplotlib"

echo.
echo   GyroAim agent
echo   ---------------------------------------------
echo.

rem The py launcher is the reliable one on Windows; plain python is the
rem fallback for installs that skipped it.
set "PY=py"
where py >nul 2>&1 || set "PY=python"
where %PY% >nul 2>&1 || goto :nopython

rem Import-check rather than pip-check: it is instant when everything is
rem already present, which is every run after the first.
%PY% -c "import websockets, pynput, mss, numpy, PIL, cv2, ultralytics" >nul 2>&1
if errorlevel 1 (
  echo   First run - installing dependencies, this takes a minute...
  echo.
  %PY% -m pip install --quiet --disable-pip-version-check websockets pynput mss numpy pillow opencv-python-headless ultralytics
  if errorlevel 1 goto :nodeps
  echo   Done.
  echo.
)

%PY% server.py
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (
  echo   The agent stopped with error code %CODE%.
) else (
  echo   The agent has stopped.
)
echo.
pause
exit /b %CODE%

:nopython
echo   Python was not found on this PC.
echo.
echo   Install it from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:nodeps
echo.
echo   Could not install the dependencies. Check your internet connection,
echo   then run this file again.
echo.
pause
exit /b 1
