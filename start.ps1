<#
    PhotoOrganizer AI - Windows PowerShell start script

    Launches the desktop GUI. On first run it creates a local virtual
    environment (".venv") and installs the application with its GUI + EXIF
    + geo extras; later runs reuse it.

    Usage (from PowerShell, in the project folder):
        ./start.ps1

    If script execution is blocked, allow it for the current session with:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

    Requirements: Python 3.12+ on PATH.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

function Get-BootstrapPython {
    foreach ($candidate in @("python", "py")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { return $candidate }
    }
    throw "Python 3.12+ was not found on PATH. Install it from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH')."
}

if (-not (Test-Path $pythonExe)) {
    $bootstrap = Get-BootstrapPython
    Write-Host "[setup] Creating virtual environment in '.venv' ..." -ForegroundColor Cyan
    & $bootstrap -m venv $venvDir
    Write-Host "[setup] Upgrading pip ..." -ForegroundColor Cyan
    & $pythonExe -m pip install --upgrade pip
    Write-Host "[setup] Installing PhotoOrganizer AI (this can take a few minutes) ..." -ForegroundColor Cyan
    & $pythonExe -m pip install -e ".[gui,exif,geo]"
}

Write-Host "[run] Starting PhotoOrganizer AI ..." -ForegroundColor Green
& $pythonExe -m photo_organizer.gui.app
exit $LASTEXITCODE
