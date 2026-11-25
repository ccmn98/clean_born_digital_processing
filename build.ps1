# Set the working directory to the project root
Set-Location -LiteralPath $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: .venv was not found." -ForegroundColor Red
    Write-Host "Expected: $Python"
    exit 1
}

$BuildDir = Join-Path $PSScriptRoot "build"
$DistDir  = Join-Path $PSScriptRoot "dist"

Write-Host "Stopping any running BornDigitalProcessing process..." -ForegroundColor Yellow
Stop-Process -Name "BornDigitalProcessing" -Force -ErrorAction SilentlyContinue

Write-Host "Removing previous build folders..." -ForegroundColor Yellow

if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir -ErrorAction Stop
}

if (Test-Path $DistDir) {
    Remove-Item -Recurse -Force $DistDir -ErrorAction Stop
}

Write-Host "Building BornDigitalProcessing..." -ForegroundColor Cyan
Write-Host "Using Python: $Python"
Write-Host ""

& $Python -m PyInstaller --clean --noconfirm --onedir `
    --windowed `
    --name BornDigitalProcessing `
    --icon "core\images\US-LibraryOfCongress-Logo.ico" `
    --add-data "core\images\US-LibraryOfCongress-Logo.ico:core\images" `
    --add-data "core\help_docs:core\help_docs" `
    --add-data "core\version.json:core" `
    --add-data "core\executables:core\executables" `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " BUILD COMPLETED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable:"
    Write-Host "dist\BornDigitalProcessing\BornDigitalProcessing.exe"
}
else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host " BUILD FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit $LASTEXITCODE
}