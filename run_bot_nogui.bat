@echo off
REM ============================================================
REM   Earn Bot - Headless / no-GUI Windows launcher
REM   Made by @codex_here
REM   Use this on VPS or when you don't want the dashboard
REM ============================================================
title Earn Bot - Headless Mode
color 0B
cd /d "%~dp0"

echo ============================================================
echo   EARN BOT - Headless Mode (no dashboard)
echo                made by @codex_here
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not installed. https://python.org/downloads/
    pause
    exit /b 1
)

python -m pip install --quiet MetaTrader5 pandas numpy

python earn_bot.py --no-gui
pause
