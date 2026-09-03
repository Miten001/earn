@echo off
REM Windows: double-click karo. Window minimize karke chhod do, 24x7 chalega.
cd /d %~dp0
python miner.py %*
pause
