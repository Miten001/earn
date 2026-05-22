@echo off
REM ============================================================
REM   Earn Scalper - HFT MT5 Bot Windows Launcher
REM   Made by @codex_here
REM ============================================================
title Earn Scalper - HFT Mode
color 0D
cd /d "%~dp0"

echo ============================================================
echo   EARN SCALPER - HFT-style MT5 Bot
echo                made by @codex_here
echo ============================================================
echo   Strategy   : M1 EMA(5/15) cross + RSI(7)
echo   Risk       : 1%% per trade
echo   SL / TP    : 5 / 6 pips (FX)
echo   Greedy exit: at 60%% of TP
echo   Max trades : 30 concurrent (3 per pair)
echo   Scan       : every 1 second
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not installed. Get it: https://python.org/downloads/
    pause
    exit /b 1
)

echo [*] Checking dependencies...
python -m pip install --quiet MetaTrader5 pandas numpy >nul 2>&1
echo [+] Dependencies OK.
echo.

echo Before starting:
echo   1. MT5 terminal OPEN and logged in
echo   2. AutoTrading ON (Ctrl+E in MT5)
echo   3. Tight-spread broker for best results
echo.
timeout /t 3 /nobreak >nul

python earn_scalper.py
pause
