@echo off
setlocal

title LoopSketch - Automatic Design Studio
cd /d "%~dp0"

echo Opening LoopSketch in your default browser...
start "" "%~dp0index.html"

endlocal
exit /b 0
