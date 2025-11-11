# Comprehensive USB Creation Script
# DriveRepair by commstech v0.0.1
# Creates a bootable USB drive with UEFI and BIOS support

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$UseWsl = $true
)

$ErrorActionPreference = "Stop"

Write-Host "Drive Repair Tool - Bootable USB Creator" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Validate drive letter format
if (-not $UsbDrive.EndsWith(":")) {
    $UsbDrive = $UsbDrive + ":"
}

Write-Host "Target USB Drive: $UsbDrive" -ForegroundColor Yellow
Write-Host ""

# Step 1: Check if WSL is available (if using WSL)
if ($UseWsl -and -not $SkipBuild) {
    $wslAvailable = Get-Command wsl -ErrorAction SilentlyContinue
    if (-not $wslAvailable) {
        Write-Host "WARNING: WSL not found. Bootloaders cannot be built." -ForegroundColor Yellow
        Write-Host "You can:" -ForegroundColor White
        Write-Host "  1. Install WSL: wsl --install" -ForegroundColor Cyan
        Write-Host "  2. Use -SkipBuild and provide pre-built bootloaders" -ForegroundColor Cyan
        Write-Host ""
        $continue = Read-Host "Continue with USB setup only? (y/n)"
        if ($continue -ne "y") {
            exit 1
        }
        $SkipBuild = $true
    }
}

# Step 2: Build bootloaders (if not skipping)
if (-not $SkipBuild) {
    Write-Host "Step 1: Building bootloaders..." -ForegroundColor Cyan
    Write-Host ""
    
    if ($UseWsl) {
        Write-Host "Building in WSL..." -ForegroundColor Yellow
        & "$PSScriptRoot\build_in_wsl.ps1" 2>&1 | Out-Null
        
        # Check for built bootloaders
        $uefiX64 = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
        if (Test-Path $uefiX64) {
            Write-Host "  ✅ UEFI x64 bootloader built" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  UEFI x64 bootloader not found (build may have failed)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Building natively (may fail on Windows)..." -ForegroundColor Yellow
        & "$PSScriptRoot\build_bootloaders.ps1" 2>&1 | Out-Null
    }
    Write-Host ""
}

# Step 3: Setup USB structure
Write-Host "Step 2: Setting up USB drive structure..." -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "WARNING: Not running as Administrator!" -ForegroundColor Yellow
    Write-Host "Disk operations require administrator privileges." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Cyan
    Write-Host "  1. Right-click PowerShell" -ForegroundColor White
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor White
    Write-Host "  3. Run this script again" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use the existing setup script:" -ForegroundColor Cyan
    Write-Host "  .\scripts\setup_usb_only.ps1 -UsbDrive `"$UsbDrive`"" -ForegroundColor White
    exit 1
}

# Use the existing setup script which has better error handling
Write-Host "Using setup script..." -ForegroundColor Yellow
& "$PSScriptRoot\setup_usb_only.ps1" -UsbDrive $UsbDrive

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: USB setup failed" -ForegroundColor Red
    exit 1
}

$efiDriveLetter = $UsbDrive.TrimEnd(":")

# Step 4: Copy bootloaders
Write-Host "Step 3: Copying bootloaders..." -ForegroundColor Cyan
Write-Host ""

$bootloadersCopied = 0

# UEFI x64
$uefiX64Source = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
$uefiX64Boot = "$efiDriveLetter`:\EFI\BOOT\BOOTX64.EFI"
$uefiX64App = "$efiDriveLetter`:\EFI\DriveRepair\DRIVEREPAIRX64.EFI"

if (Test-Path $uefiX64Source) {
    Copy-Item $uefiX64Source $uefiX64Boot -Force
    Copy-Item $uefiX64Source $uefiX64App -Force
    Write-Host "  ✅ UEFI x64 bootloader copied" -ForegroundColor Green
    $bootloadersCopied++
} else {
    Write-Host "  ⚠️  UEFI x64 bootloader not found: $uefiX64Source" -ForegroundColor Yellow
}

# UEFI ARM64
$uefiARM64Source = "src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi"
$uefiARM64Boot = "$efiDriveLetter`:\EFI\BOOT\BOOTAA64.EFI"
$uefiARM64App = "$efiDriveLetter`:\EFI\DriveRepair\DRIVEREPAIRAA64.EFI"

if (Test-Path $uefiARM64Source) {
    Copy-Item $uefiARM64Source $uefiARM64Boot -Force
    Copy-Item $uefiARM64Source $uefiARM64App -Force
    Write-Host "  ✅ UEFI ARM64 bootloader copied" -ForegroundColor Green
    $bootloadersCopied++
} else {
    Write-Host "  ⚠️  UEFI ARM64 bootloader not found (optional)" -ForegroundColor Gray
}

# BIOS (if available)
$biosSource = "src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios"
if (Test-Path $biosSource) {
    # BIOS bootloader would need special handling (MBR, etc.)
    Write-Host "  ⚠️  BIOS bootloader found but requires MBR setup (not implemented)" -ForegroundColor Yellow
}

Write-Host ""

# Step 5: Verification
Write-Host "Step 4: Verifying installation..." -ForegroundColor Cyan
Write-Host ""

$allGood = $true

if (Test-Path $uefiX64Boot) {
    Write-Host "  ✅ BOOTX64.EFI found" -ForegroundColor Green
} else {
    Write-Host "  ❌ BOOTX64.EFI NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path $uefiARM64Boot) {
    Write-Host "  ✅ BOOTAA64.EFI found" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  BOOTAA64.EFI not found (optional)" -ForegroundColor Yellow
}

Write-Host ""

# Final summary
Write-Host "=========================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✅ Bootable USB created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "USB Drive: $UsbDrive" -ForegroundColor White
    Write-Host "Bootloaders copied: $bootloadersCopied" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Safely eject the USB drive" -ForegroundColor White
    Write-Host "  2. Insert into target system" -ForegroundColor White
    Write-Host "  3. Boot from USB (UEFI mode)" -ForegroundColor White
    Write-Host "  4. Test the application" -ForegroundColor White
} else {
    Write-Host "⚠️  USB created but bootloaders are missing!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To fix:" -ForegroundColor Cyan
    Write-Host "  1. Build bootloaders: .\scripts\build_in_wsl.ps1" -ForegroundColor White
    Write-Host "  2. Copy manually: .\scripts\copy_bootloaders.ps1 -UsbDrive `"$UsbDrive`"" -ForegroundColor White
}

Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

