@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Surf Bash CAPTCHA Clicker
color 0A
cd /d "%~dp0"

set "LOG=%~dp0launcher_log.txt"
>> "%LOG%" echo.
>> "%LOG%" echo ===== %DATE% %TIME% =====
>> "%LOG%" echo [1] folder: %CD%
>> "%LOG%" echo [1] args: %*

echo ==================================================
echo    Surf Bash CAPTCHA Clicker
echo ==================================================
echo.

set "PYCMD="
where python >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PYCMD=py"
)
if not defined PYCMD (
    where python3 >nul 2>nul
    if not errorlevel 1 set "PYCMD=python3"
)

if defined PYCMD (
    %PYCMD% --version >nul 2>nul
    if errorlevel 1 set "PYCMD="
)
>> "%LOG%" echo [2] python: %PYCMD%

if not defined PYCMD (
    echo [SETUP] Python nahi mila - winget se install kar raha hoon...
    echo         ^(internet chahiye, 1-2 minute lag sakte hain^)
    >> "%LOG%" echo [3] winget install Python.Python.3.12
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    where python >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
    if not defined PYCMD (
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYCMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

if defined PYCMD (
    >> "%LOG%" echo [3] python ready: %PYCMD%
    echo [OK] Python: %PYCMD%
    echo.
    rem ---- SELF-UPDATE: purana clicker.py delete hoke naya download hota hai ----
    set "NEWPY=%~dp0clicker_new.py"
    set "URL=https://raw.githubusercontent.com/Miten001/earn/main/clicker.py"
    if exist "%~dp0no_update.txt" (
        echo [SKIP] no_update.txt mila - update band
        >> "%LOG%" echo [4] update skipped (no_update.txt)
    ) else (
        echo [SETUP] latest clicker.py download kar raha hoon...
        >> "%LOG%" echo [4] download clicker.py (self-update)
        del /q "%NEWPY%" >nul 2>nul
        curl -L -s -S -o "%NEWPY%" "%URL%"
        set "NEWOK="
        if exist "%NEWPY%" for %%F in ("%NEWPY%") do if %%~zF GTR 20000 set "NEWOK=1"
        if not defined NEWOK (
            rem curl fail (ya purana Windows) -> PowerShell se dobara
            del /q "%NEWPY%" >nul 2>nul
            powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%NEWPY%' -UseBasicParsing } catch { exit 1 }"
            if exist "%NEWPY%" for %%F in ("%NEWPY%") do if %%~zF GTR 20000 set "NEWOK=1"
        )
        if defined NEWOK (
            if exist "clicker.py" del /q "clicker.py"
            move /y "%NEWPY%" "%~dp0clicker.py" >nul
            echo [OK] clicker.py latest version ready
            >> "%LOG%" echo [4] clicker.py updated
        ) else (
            if exist "%NEWPY%" del /q "%NEWPY%" >nul 2>nul
            >> "%LOG%" echo [4] download FAILED - purani copy check
            if exist "clicker.py" (
                echo [WARN] Download fail - internet check karo. Purani clicker.py se start kar raha hoon
            ) else (
                echo [ERROR] clicker.py download bhi nahi hua aur purani copy bhi nahi hai!
            )
        )
    )
    if exist "clicker.py" (
        echo [RUN] Clicker start ho raha hai...
        echo.
        >> "%LOG%" echo [5] run: %PYCMD% -u clicker.py %*
        %PYCMD% -u "clicker.py" %*
        >> "%LOG%" echo [6] exit code: !ERRORLEVEL!
        if errorlevel 1 (
            echo.
            echo [NOTE] Kuch error aaya tha - clicker_log.txt aur launcher_log.txt dekho
        )
    ) else (
        echo [ERROR] clicker.py download nahi hua!
        echo         Internet check karo, ya file manually isi folder me rakho.
        >> "%LOG%" echo [4] DOWNLOAD FAILED
    )
) else (
    echo [ERROR] Python install nahi ho paya.
    echo         Manual install: https://www.python.org/downloads/
    echo         Install karte waqt "Add Python to PATH" tick karo.
    >> "%LOG%" echo [3] PYTHON NOT FOUND
    start "" https://www.python.org/downloads/
)

echo.
echo --------------------------------------------------
echo   Logs : launcher_log.txt  ^|  clicker_log.txt
echo   Check: clicker.bat --selftest
echo   Debug: clicker.bat --debug --dry-run
echo   Window band karne ke liye koi bhi key dabao...
echo --------------------------------------------------
pause >nul
