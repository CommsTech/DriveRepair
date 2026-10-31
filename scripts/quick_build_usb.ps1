# =============================================================================
# GATE 0 SAFETY: Destructive USB provisioning is DISABLED pending safety gates.
# This script will NOT erase disks, format media, or write bootloaders.
# Original body preserved below but is unreachable.
# =============================================================================
Write-Host "ERROR: Destructive USB provisioning is DISABLED pending Gate 0 safety gates." -ForegroundColor Red
Write-Host "Refusing to touch USB/disk media. Exit code 2." -ForegroundColor Red
exit 2

<# DISABLED_ORIGINAL_BODY
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

# Temporarily replace Cargo.toml with standalone version to avoid library deps
Write-Host "  Using standalone Cargo.toml (no library dependencies)" -ForegroundColor Yellow

# Create build script that temporarily swaps Cargo.toml files
$buildScriptContent = @"
#!/bin/bash
cd '$wslPath/src/boot/uefi'
source ~/.cargo/env 2>/dev/null || true
rustup target add x86_64-unknown-uefi 2>/dev/null || true
# Backup original and use standalone
cp Cargo.toml Cargo.toml.orig 2>/dev/null || true
cp Cargo_standalone.toml Cargo.toml
cargo build --bin drive-repair-uefi-standalone --target x86_64-unknown-uefi --release
BUILD_EXIT=`$?
# Restore original
mv Cargo.toml.orig Cargo.toml 2>/dev/null || true
exit `$BUILD_EXIT
"@

$binName = "drive-repair-uefi-standalone"

$scriptFile = "$env:TEMP\build_bootloader.sh"
# Write with Unix line endings (LF only) - each line separately
$lines = $buildScriptContent -split "`r?`n"
$lines | ForEach-Object {
    if ($_.Trim() -ne "") {
        Add-Content -Path $scriptFile -Value $_ -NoNewline -Encoding ASCII
        Add-Content -Path $scriptFile -Value "`n" -NoNewline -Encoding ASCII
    }
}

$wslScriptPath = $scriptFile -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslScriptPath = $wslScriptPath.ToLower()

Write-Host "  Building..." -ForegroundColor Yellow
$buildOutput = wsl bash $wslScriptPath 2>&1
$buildExitCode = $LASTEXITCODE

# Show build output
Write-Host "Build output:" -ForegroundColor Gray
$buildOutput | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

if ($buildExitCode -ne 0) {
    Write-Host "  ❌ Build failed (exit code: $buildExitCode)" -ForegroundColor Red
    Remove-Item $scriptFile -ErrorAction SilentlyContinue
    exit 1
}

# Check if build actually succeeded by looking for the file
$checkFile = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\$binName.efi"
if (-not (Test-Path $checkFile)) {
    Write-Host "  ⚠️  Build reported success but .efi file not found" -ForegroundColor Yellow
    Write-Host "  This usually means the build failed silently" -ForegroundColor Yellow
} else {
    Write-Host "  ✅ Build successful!" -ForegroundColor Green
}
Remove-Item $scriptFile -ErrorAction SilentlyContinue

# Find the actual .efi file that was created
$possiblePaths = @(
    "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\$binName.efi",
    "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\*.efi"
)

$efiFile = $null
foreach ($path in $possiblePaths) {
    $found = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        $efiFile = $found.FullName
        break
    }
}

# If not found, search in the target directory
if (-not $efiFile) {
    $targetDir = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release"
    if (Test-Path $targetDir) {
        $found = Get-ChildItem -Path $targetDir -Filter "*.efi" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $efiFile = $found.FullName
        }
    }
}

if ($efiFile) {
    Write-Host "  Found: $efiFile" -ForegroundColor Cyan
    $efiSource = $efiFile
} else {
    Write-Host "  ⚠️  Could not locate .efi file, using expected path" -ForegroundColor Yellow
    $efiSource = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\$binName.efi"
}

Write-Host ""

# Step 3: Copy to USB
Write-Host "Step 3: Copying to USB..." -ForegroundColor Cyan

$efiBootPath = "$efiDriveLetter`:\EFI\BOOT\BOOTX64.EFI"
$efiAppPath = "$efiDriveLetter`:\EFI\DriveRepair\DRIVEREPAIRX64.EFI"

if (-not (Test-Path $efiSource)) {
    Write-Host "  ❌ Bootloader not found: $efiSource" -ForegroundColor Red
    Write-Host ""
    Write-Host "Searching for any .efi files..." -ForegroundColor Yellow
    $allEfi = Get-ChildItem -Path "$projectPath\src\boot\uefi\target" -Filter "*.efi" -Recurse -ErrorAction SilentlyContinue
    if ($allEfi) {
        Write-Host "Found .efi files:" -ForegroundColor Cyan
        $allEfi | ForEach-Object { Write-Host "  $($_.FullName)" -ForegroundColor White }
        $efiSource = $allEfi[0].FullName
        Write-Host "Using: $efiSource" -ForegroundColor Green
    } else {
        Write-Host "No .efi files found. Build may have failed silently." -ForegroundColor Red
        exit 1
    }
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

# Try to copy - if it fails due to permissions, provide manual instructions
try {
    # Remove existing files if they exist
    if (Test-Path $efiBootPath) {
        Remove-Item $efiBootPath -Force -ErrorAction Stop
    }
    if (Test-Path $efiAppPath) {
        Remove-Item $efiAppPath -Force -ErrorAction Stop
    }
    
    Copy-Item $efiSource $efiBootPath -Force -ErrorAction Stop
    Copy-Item $efiSource $efiAppPath -Force -ErrorAction Stop
} catch {
    Write-Host "  ⚠️  Copy failed (permission denied)" -ForegroundColor Yellow
    Write-Host "  The bootloader was built successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Manual copy (run PowerShell as Administrator):" -ForegroundColor Cyan
    Write-Host "    Copy-Item `"$efiSource`" `"$efiBootPath`" -Force" -ForegroundColor White
    Write-Host "    Copy-Item `"$efiSource`" `"$efiAppPath`" -Force" -ForegroundColor White
    Write-Host ""
    Write-Host "  Or use the file explorer to copy manually." -ForegroundColor White
    exit 0  # Exit successfully since build worked
}

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


#>
