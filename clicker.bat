@echo off
title Screen CAPTCHA Clicker
color 0A
setlocal EnableDelayedExpansion

echo ==================================================
echo    Screen CAPTCHA Clicker - Auto Setup
echo ==================================================
echo.

:: ---------- Step 1: Python 3 dhoondho ----------
set "PYCMD="

python --version >nul 2>nul
if "!errorlevel!"=="0" goto :check_py3
goto :try_launcher

:check_py3
python --version 2>nul | findstr /C:"Python 3" >nul
if "!errorlevel!"=="0" set "PYCMD=python"
goto :after_find

:try_launcher
py -3 --version >nul 2>nul
if "!errorlevel!"=="0" set "PYCMD=py -3"

:after_find
if defined PYCMD goto :python_ready

:: ---------- Step 2: Python na mile to auto-install karo ----------
echo [SETUP] Python nahi mila - download kar raha hoon...
echo         (internet chahiye, thoda time lagega)
echo.

powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"

if not exist "%TEMP%\python-installer.exe" goto :dl_fail

echo [SETUP] Python install kar raha hoon...
start /wait "" "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1

set "PYCMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "!PYCMD!" goto :install_fail

echo [SETUP] Python install ho gaya!
echo.
goto :python_ready

:dl_fail
echo.
echo [ERROR] Python download nahi ho paya!
echo Internet check karo, phir dobara double-click karo.
echo.
pause
exit /b 1

:install_fail
echo.
echo [ERROR] Python install hone ke baad bhi nahi mila!
echo Manual install karo: https://www.python.org/downloads
echo Install karte time "Add Python to PATH" tick zaroor lagana.
echo.
pause
exit /b 1

:python_ready
echo Python ready hai. Clicker start kar raha hoon...
echo.

:: ---------- Step 3: clicker.py check karo (na mile to GitHub se lo) ----------
cd /d "%~dp0"
if exist "%~dp0clicker.py" goto :run_clicker

echo [SETUP] clicker.py nahi mila - GitHub se download kar raha hoon...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Miten001/earn/main/clicker.py' -OutFile '%~dp0clicker.py'"
echo.

:run_clicker
:: ---------- Step 4: Clicker chalao ----------
!PYCMD! "%~dp0clicker.py"

echo.
pause
