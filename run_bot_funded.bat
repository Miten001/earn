@echo off
REM ============================================================
REM   Earn Bot FUNDED - Prop Firm Edition Windows Launcher
REM   Made by @codex_here
REM ============================================================
title Earn Bot FUNDED - Prop Firm
color 0E
cd /d "%~dp0"

echo ============================================================
echo   EARN BOT FUNDED - Prop Firm Edition
echo                made by @codex_here
echo ============================================================
echo   Risk per trade  : 1%%
echo   Daily loss cap  : -3%%
echo   Max drawdown    : -8%%
echo   Max trades      : 3 simultaneous
echo   Friday EOD      : auto-close all
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not installed. Get it: https://python.org/downloads/
    pause
    exit /b 1
)

echo [*] Checking dependencies...
python -m pip install --quiet MetaTrader5 pandas numpy matplotlib >nul 2>&1
echo [+] Dependencies OK.
echo.

echo Before starting:
echo   1. MT5 terminal OPEN and logged in
echo   2. AutoTrading ON (Ctrl+E in MT5)
echo   3. Pass your prop firm rules (check daily limit etc)
echo.
timeout /t 3 /nobreak >nul

python earn_bot_funded.py
echo.
pause
