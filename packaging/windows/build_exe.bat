@echo off
REM ===================================================================
REM  Build the standalone PhotoOrganizer AI executable with PyInstaller.
REM
REM  Run from the PROJECT ROOT (the folder containing pyproject.toml):
REM      packaging\windows\build_exe.bat
REM
REM  Output: dist\PhotoOrganizerAI\PhotoOrganizerAI.exe
REM ===================================================================

setlocal enableextensions
cd /d "%~dp0..\.."

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [setup] Creating virtual environment ...
    where python >nul 2>&1 && (python -m venv "%VENV_DIR%") || (py -3 -m venv "%VENV_DIR%")
)

echo [setup] Installing app + packaging dependencies ...
"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install -e ".[gui,exif,geo,package]"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo [build] Cleaning previous build ...
if exist build rmdir /s /q build
if exist "dist\PhotoOrganizerAI" rmdir /s /q "dist\PhotoOrganizerAI"

echo [build] Running PyInstaller ...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm "packaging\windows\PhotoOrganizerAI.spec"
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [done] Executable created at: dist\PhotoOrganizerAI\PhotoOrganizerAI.exe
echo        (Run build_installer.bat next to produce a Setup installer.)
endlocal
