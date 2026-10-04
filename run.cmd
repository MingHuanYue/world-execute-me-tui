@echo off
REM world.execute(me); TUI MV - one-click build for Windows
REM Double-click this file. Requires Python 3.9+ installed.
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYEXE=py -3"
  goto :havepy
)
where python >nul 2>nul
if not errorlevel 1 (
  set "PYEXE=python"
  goto :havepy
)

echo.
echo   [X] Python not found.
echo.
echo       Install Python 3.9 or newer from:
echo         https://www.python.org/downloads/
echo       During setup, check "Add python.exe to PATH".
echo.
pause
exit /b 1

:havepy
echo.
echo   Starting one-click build.
echo   First run creates .venv and downloads dependencies.
echo.

%PYEXE% "%~dp0oneclick.py" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo   Done. The video is in the "out" folder.
) else (
  echo   Stopped with exit code %RC%.
)
echo.
pause
exit /b %RC%
