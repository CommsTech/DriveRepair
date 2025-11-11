# Complete USB Build and Installation Script
# DriveRepair by commstech v0.0.1
# Builds minimal bootloader and installs to USB

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipUsbSetup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "Drive Repair Tool - Complete USB Builder" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Validate drive letter
if (-not $UsbDrive.EndsWith(":")) {
    $UsbDrive = $UsbDrive + ":"
}

Write-Host "Target USB Drive: $UsbDrive" -ForegroundColor Yellow
Write-Host ""

# Check if running as administrator (for USB setup)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Step 1: Setup USB structure (if needed)
if (-not $SkipUsbSetup) {
    if (-not $isAdmin) {
        Write-Host "WARNING: Not running as Administrator!" -ForegroundColor Yellow
        Write-Host "USB setup requires administrator privileges." -ForegroundColor Yellow
        Write-Host "Skipping USB setup. Using existing structure..." -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Host "Step 1: Setting up USB structure..." -ForegroundColor Cyan
        & "$PSScriptRoot\setup_usb_only.ps1" -UsbDrive $UsbDrive
        if ($LASTEXITCODE -ne 0) {
            Write-Host "USB setup failed, but continuing..." -ForegroundColor Yellow
        }
        Write-Host ""
    }
}

# Step 2: Install build tools in WSL
Write-Host "Step 2: Installing build tools in WSL..." -ForegroundColor Cyan
Write-Host ""

$wslCheck = wsl bash -c "which gcc > /dev/null 2>&1 && echo 'installed' || echo 'not_installed'"
if ($wslCheck -eq "not_installed") {
    Write-Host "Build tools not found. Installing..." -ForegroundColor Yellow
    Write-Host "You may be prompted for your WSL password." -ForegroundColor Yellow
    Write-Host ""
    
    # Try to install without password (if sudo is configured)
    $installOutput = wsl bash -c "sudo -n apt update 2>&1 && sudo -n apt install -y build-essential 2>&1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Build tools installed" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Automatic installation failed (password required)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please run this command manually in WSL:" -ForegroundColor Cyan
        Write-Host "  wsl" -ForegroundColor White
        Write-Host "  sudo apt update && sudo apt install -y build-essential" -ForegroundColor White
        Write-Host ""
        $continue = Read-Host "Press Enter after installing build tools, or 'skip' to try anyway"
        if ($continue -eq "skip") {
            Write-Host "Continuing without build tools..." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  ✅ Build tools already installed" -ForegroundColor Green
}
Write-Host ""

# Step 3: Build minimal bootloader
Write-Host "Step 3: Building minimal bootloader..." -ForegroundColor Cyan
Write-Host ""

$projectPath = (Get-Location).Path
$wslPath = $projectPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslPath = $wslPath.ToLower()

# Fix line endings by using a here-document in WSL
$buildScript = @"
cd '$wslPath/src/boot/uefi'
source ~/.cargo/env 2>/dev/null || true
rustup target add x86_64-unknown-uefi 2>/dev/null
cargo build --bin drive-repair-uefi-minimal --target x86_64-unknown-uefi --release 2>&1
"@

Write-Host "Building in WSL..." -ForegroundColor Yellow

# Write script to temp file to avoid line ending issues
$tempScript = [System.IO.Path]::GetTempFileName()
$buildScript | Out-File -FilePath $tempScript -Encoding ASCII -NoNewline
$wslScriptPath = $tempScript -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslScriptPath = $wslScriptPath.ToLower()

$buildOutput = wsl bash $wslScriptPath
$buildExitCode = $LASTEXITCODE

# Clean up temp file
Remove-Item $tempScript -ErrorAction SilentlyContinue

if ($buildExitCode -eq 0) {
    Write-Host "  ✅ Build successful!" -ForegroundColor Green
} else {
    Write-Host "  ❌ Build failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  1. Build tools not installed: sudo apt install -y build-essential" -ForegroundColor White
    Write-Host "  2. Rust not installed in WSL: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh" -ForegroundColor White
    Write-Host ""
    Write-Host "Build output (last 20 lines):" -ForegroundColor Yellow
    $buildOutput | Select-Object -Last 20 | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
    Write-Host ""
    Write-Host "Trying to continue anyway..." -ForegroundColor Yellow
}

Write-Host ""

# Step 4: Copy bootloader to USB
Write-Host "Step 4: Copying bootloader to USB..." -ForegroundColor Cyan
Write-Host ""

$efiSource = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi-minimal.efi"
$efiDriveLetter = $UsbDrive.TrimEnd(":")
$efiBootPath = "$efiDriveLetter`:\EFI\BOOT\BOOTX64.EFI"
$efiAppPath = "$efiDriveLetter`:\EFI\DriveRepair\DRIVEREPAIRX64.EFI"

if (Test-Path $efiSource) {
    # Ensure directories exist
    $bootDir = "$efiDriveLetter`:\EFI\BOOT"
    $appDir = "$efiDriveLetter`:\EFI\DriveRepair"
    
    if (-not (Test-Path $bootDir)) {
        New-Item -ItemType Directory -Path $bootDir -Force | Out-Null
    }
    if (-not (Test-Path $appDir)) {
        New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    }
    
    # Copy bootloader
    Copy-Item $efiSource $efiBootPath -Force
    Copy-Item $efiSource $efiAppPath -Force
    
    Write-Host "  ✅ Bootloader copied to:" -ForegroundColor Green
    Write-Host "     $efiBootPath" -ForegroundColor Cyan
    Write-Host "     $efiAppPath" -ForegroundColor Cyan
} else {
    Write-Host "  ❌ Bootloader not found: $efiSource" -ForegroundColor Red
    Write-Host ""
    Write-Host "Build may have failed. Check build output above." -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 5: Verification
Write-Host "Step 5: Verifying installation..." -ForegroundColor Cyan
Write-Host ""

$allGood = $true

if (Test-Path $efiBootPath) {
    $fileSize = (Get-Item $efiBootPath).Length
    Write-Host "  ✅ BOOTX64.EFI found ($([math]::Round($fileSize/1KB, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "  ❌ BOOTX64.EFI NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path $efiAppPath) {
    Write-Host "  ✅ DRIVEREPAIRX64.EFI found" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  DRIVEREPAIRX64.EFI not found" -ForegroundColor Yellow
}

Write-Host ""

# Final summary
Write-Host "=========================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✅ Bootable USB created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "USB Drive: $UsbDrive" -ForegroundColor White
    Write-Host "Bootloader: Minimal UEFI bootloader" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Safely eject the USB drive" -ForegroundColor White
    Write-Host "  2. Insert into target system" -ForegroundColor White
    Write-Host "  3. Boot from USB (UEFI mode)" -ForegroundColor White
    Write-Host "  4. You should see the DriveRepair welcome screen" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: This is a minimal bootloader that displays a message." -ForegroundColor Yellow
    Write-Host "Full functionality will be added once compilation errors are fixed." -ForegroundColor Yellow
} else {
    Write-Host "⚠️  USB setup incomplete" -ForegroundColor Yellow
    Write-Host "Check errors above and try again." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

