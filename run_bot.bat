@echo off
REM ============================================================
REM   Earn Bot - One-click Windows launcher
REM   Made by @codex_here
REM ============================================================
title Earn Bot - SMC/ICT MT5 Trader
color 0A
cd /d "%~dp0"

echo ============================================================
echo   EARN BOT - Windows Launcher
echo                made by @codex_here
echo ============================================================
echo.

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not installed or not in PATH.
    echo [!] Download Python 3.10+ from: https://python.org/downloads/
    echo [!] During install, CHECK "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [*] Python detected:
python --version
echo.

REM ---- Install / update dependencies (silent if already present) ----
echo [*] Checking dependencies...
python -m pip install --quiet --upgrade pip >nul 2>&1
python -m pip install --quiet MetaTrader5 pandas numpy matplotlib

if errorlevel 1 (
    echo [!] Dependency install failed. Check internet connection.
    pause
    exit /b 1
)
echo [+] Dependencies OK.
echo.

REM ---- Sanity reminder ----
echo ============================================================
echo   Before bot starts, make sure:
echo     1. MT5 terminal is OPEN and logged in
echo     2. AutoTrading is ON (top-right button or Ctrl+E)
echo     3. Credentials filled in earn_bot.py
echo ============================================================
echo.
timeout /t 3 /nobreak >nul

REM ---- Run bot ----
python earn_bot.py
set EXITCODE=%errorlevel%

echo.
echo ============================================================
echo   Bot exited with code %EXITCODE%
echo ============================================================
pause
