# Quick USB Build Script
# DriveRepair by commstech v0.0.1
# Simplified version that handles WSL setup better

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive
)

Write-Host "Drive Repair Tool - Quick USB Builder" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

if (-not $UsbDrive.EndsWith(":")) {
    $UsbDrive = $UsbDrive + ":"
}

$efiDriveLetter = $UsbDrive.TrimEnd(":")

# Step 1: Check/Install build tools
Write-Host "Step 1: Checking WSL build tools..." -ForegroundColor Cyan

$hasGcc = wsl bash -c "which gcc > /dev/null 2>&1 && echo 'yes' || echo 'no'"
if ($hasGcc -eq "no") {
    Write-Host "  Build tools not found!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please install build tools in WSL:" -ForegroundColor Cyan
    Write-Host "  1. Open WSL: wsl" -ForegroundColor White
    Write-Host "  2. Run: sudo apt update && sudo apt install -y build-essential" -ForegroundColor White
    Write-Host ""
    Write-Host "Or configure passwordless sudo:" -ForegroundColor Cyan
    Write-Host "  wsl" -ForegroundColor White
    Write-Host "  sudo visudo" -ForegroundColor White
    Write-Host "  Add: commstech ALL=(ALL) NOPASSWD: ALL" -ForegroundColor White
    Write-Host ""
    exit 1
} else {
    Write-Host "  ✅ Build tools found" -ForegroundColor Green
}
Write-Host ""

# Step 2: Build
Write-Host "Step 2: Building minimal bootloader..." -ForegroundColor Cyan

$projectPath = (Get-Location).Path
$wslPath = $projectPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslPath = $wslPath.ToLower()

# Create build script file
$buildScriptContent = @"
#!/bin/bash
set -e
cd '$wslPath/src/boot/uefi'
source ~/.cargo/env 2>/dev/null || true
rustup target add x86_64-unknown-uefi 2>/dev/null || true
cargo build --bin drive-repair-uefi-minimal --target x86_64-unknown-uefi --release
"@

$scriptFile = "$env:TEMP\build_bootloader.sh"
$buildScriptContent | Out-File -FilePath $scriptFile -Encoding ASCII -NoNewline
$wslScriptPath = $scriptFile -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslScriptPath = $wslScriptPath.ToLower()

Write-Host "  Building..." -ForegroundColor Yellow
wsl bash $wslScriptPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Build failed" -ForegroundColor Red
    Remove-Item $scriptFile -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "  ✅ Build successful!" -ForegroundColor Green
Remove-Item $scriptFile -ErrorAction SilentlyContinue
Write-Host ""

# Step 3: Copy to USB
Write-Host "Step 3: Copying to USB..." -ForegroundColor Cyan

$efiSource = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi-minimal.efi"
$efiBootPath = "$efiDriveLetter`:\EFI\BOOT\BOOTX64.EFI"
$efiAppPath = "$efiDriveLetter`:\EFI\DriveRepair\DRIVEREPAIRX64.EFI"

if (-not (Test-Path $efiSource)) {
    Write-Host "  ❌ Bootloader not found: $efiSource" -ForegroundColor Red
    exit 1
}

# Ensure directories exist
$bootDir = "$efiDriveLetter`:\EFI\BOOT"
$appDir = "$efiDriveLetter`:\EFI\DriveRepair"

if (-not (Test-Path $bootDir)) {
    New-Item -ItemType Directory -Path $bootDir -Force | Out-Null
}
if (-not (Test-Path $appDir)) {
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
}

Copy-Item $efiSource $efiBootPath -Force
Copy-Item $efiSource $efiAppPath -Force

Write-Host "  ✅ Copied to:" -ForegroundColor Green
Write-Host "     $efiBootPath" -ForegroundColor Cyan
Write-Host "     $efiAppPath" -ForegroundColor Cyan
Write-Host ""

# Step 4: Verify
Write-Host "Step 4: Verification..." -ForegroundColor Cyan

if (Test-Path $efiBootPath) {
    $fileSize = (Get-Item $efiBootPath).Length
    Write-Host "  ✅ BOOTX64.EFI found ($([math]::Round($fileSize/1KB, 2)) KB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "✅ Bootable USB ready!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Safely eject USB drive" -ForegroundColor White
    Write-Host "  2. Boot from USB on target system" -ForegroundColor White
    Write-Host "  3. You should see the DriveRepair welcome screen" -ForegroundColor White
} else {
    Write-Host "  ❌ Verification failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

