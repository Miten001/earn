@echo off
setlocal EnableExtensions
title Surf Bash CAPTCHA Clicker
color 0A
cd /d "%~dp0"

echo ==================================================
echo    Surf Bash CAPTCHA Clicker
echo ==================================================
echo.

set "PYCMD="
where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD where py >nul 2>nul && set "PYCMD=py"

if not defined PYCMD (
    echo [ERROR] Python nahi mila!
    echo.
    echo   1^) Browser khulega - Python download page se install karo
    echo   2^) Install karte waqt "Add Python to PATH" tick ZAROOR karo
    echo   3^) Phir ye file dobara double-click karo
    echo.
    start "" https://www.python.org/downloads/
) else (
    echo [OK] Python mil gaya: %PYCMD%
    echo.
    if not exist "clicker.py" (
        echo [SETUP] clicker.py download kar raha hoon...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Miten001/earn/main/clicker.py' -OutFile 'clicker.py' -UseBasicParsing } catch { exit 1 }"
    )
    if exist "clicker.py" (
        echo [RUN] Clicker start ho raha hai...
        echo.
        %PYCMD% -u "clicker.py"
        if errorlevel 1 (
            echo.
            echo [NOTE] Clicker error ke saath band hua - clicker_log.txt check karo
        )
    ) else (
        echo [ERROR] clicker.py download nahi hua!
        echo         Internet check karo, ya file manually isi folder me rakho.
    )
)

echo.
echo ==================================================
echo   Window band karne ke liye koi bhi key dabao...
echo ==================================================
pause >nul
