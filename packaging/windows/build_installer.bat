@echo off
REM ===================================================================
REM  Build the Windows Setup installer for PhotoOrganizer AI.
REM
REM  Steps performed:
REM    1. Build the standalone executable (build_exe.bat)
REM    2. Compile installer.iss with Inno Setup's ISCC.exe
REM
REM  Prerequisite: Inno Setup 6 installed
REM  (https://jrsoftware.org/isdl.php). If ISCC.exe is not on PATH the
REM  script probes the default install locations.
REM
REM  Run from the PROJECT ROOT:
REM      packaging\windows\build_installer.bat
REM
REM  Output: dist\installer\PhotoOrganizerAI-Setup.exe
REM ===================================================================

setlocal enableextensions
cd /d "%~dp0..\.."

echo [1/2] Building the standalone executable ...
call "packaging\windows\build_exe.bat"
if errorlevel 1 (
    echo [ERROR] Executable build failed; aborting installer build.
    exit /b 1
)

REM --- Locate the Inno Setup compiler -----------------------------------
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo [ERROR] Inno Setup compiler (ISCC.exe) not found.
    echo         Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo         or compile packaging\windows\installer.iss manually.
    pause
    exit /b 1
)

echo [2/2] Compiling the installer with Inno Setup ...
"%ISCC%" "packaging\windows\installer.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo [done] Installer created at: dist\installer\PhotoOrganizerAI-Setup.exe
endlocal
