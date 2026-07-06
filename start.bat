@echo off
REM ===================================================================
REM  PhotoOrganizer AI - Windows start script
REM
REM  Double-click this file (or run it from a terminal) to launch the
REM  desktop GUI. On first run it creates a local virtual environment
REM  in ".venv" and installs the application with its GUI + EXIF + geo
REM  extras. Subsequent runs reuse that environment and start instantly.
REM
REM  Requirements: Python 3.12+ available on PATH (python.exe).
REM ===================================================================

setlocal enableextensions
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

REM --- Locate a suitable Python interpreter for bootstrapping -------------
where python >nul 2>&1
if %errorlevel%==0 (
    set "BOOTSTRAP_PY=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "BOOTSTRAP_PY=py -3"
    ) else (
        echo [ERROR] Python 3.12+ was not found on PATH.
        echo         Install it from https://www.python.org/downloads/windows/
        echo         and make sure "Add python.exe to PATH" is ticked.
        pause
        exit /b 1
    )
)

REM --- Create the virtual environment on first run -----------------------
if not exist "%PYTHON_EXE%" (
    echo [setup] Creating virtual environment in "%VENV_DIR%" ...
    %BOOTSTRAP_PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
    echo [setup] Upgrading pip ...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    echo [setup] Installing PhotoOrganizer AI (this can take a few minutes) ...
    "%PYTHON_EXE%" -m pip install -e ".[gui,exif,geo]"
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

REM --- Launch the GUI ----------------------------------------------------
echo [run] Starting PhotoOrganizer AI ...
"%PYTHON_EXE%" -m photo_organizer.gui.app
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [PhotoOrganizer AI exited with code %EXIT_CODE%]
    pause
)
endlocal & exit /b %EXIT_CODE%
