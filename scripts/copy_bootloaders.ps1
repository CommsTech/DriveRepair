# PowerShell script to copy bootloaders to USB drive
# DriveRepair by commstech v0.0.1
# Use this after building bootloaders (on Linux or other system)

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive,
    
    [Parameter(Mandatory=$false)]
    [string]$UefiX64Path = "drive-repair-uefi.efi",
    
    [Parameter(Mandatory=$false)]
    [string]$UefiARM64Path = "",
    
    [Parameter(Mandatory=$false)]
    [string]$BiosPath = ""
)

Write-Host "Drive Repair Tool - Bootloader Copy Script" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Validate drive
$driveLetter = $UsbDrive.TrimEnd('\', ':').ToUpper()
$partition = Get-Partition -DriveLetter $driveLetter -ErrorAction SilentlyContinue

if (-not $partition) {
    Write-Host "ERROR: Could not find drive $driveLetter`:" -ForegroundColor Red
    Write-Host "Available drives:" -ForegroundColor Yellow
    Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -gt 0 } | ForEach-Object {
        Write-Host "  $($_.Name):" -ForegroundColor White
    }
    exit 1
}

$espPath = "$driveLetter`:"

# Verify EFI structure exists
if (-not (Test-Path "$espPath\EFI\BOOT")) {
    Write-Host "ERROR: EFI\BOOT directory not found on $espPath" -ForegroundColor Red
    Write-Host "Please run setup_usb_only.ps1 first to create USB structure." -ForegroundColor Yellow
    exit 1
}

Write-Host "Target USB Drive: $espPath" -ForegroundColor Cyan
Write-Host ""

# Copy UEFI x64 bootloader
if (Test-Path $UefiX64Path) {
    Write-Host "Copying UEFI x64 bootloader..." -ForegroundColor Yellow
    Copy-Item -Path $UefiX64Path -Destination "$espPath\EFI\BOOT\BOOTX64.EFI" -Force
    Copy-Item -Path $UefiX64Path -Destination "$espPath\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force
    Write-Host "  ✅ UEFI x64 bootloader copied" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  UEFI x64 bootloader not found: $UefiX64Path" -ForegroundColor Yellow
}

# Copy UEFI ARM64 bootloader (if provided)
if ($UefiARM64Path -and (Test-Path $UefiARM64Path)) {
    Write-Host "Copying UEFI ARM64 bootloader..." -ForegroundColor Yellow
    Copy-Item -Path $UefiARM64Path -Destination "$espPath\EFI\BOOT\BOOTAA64.EFI" -Force
    Copy-Item -Path $UefiARM64Path -Destination "$espPath\EFI\DriveRepair\DRIVEREPAIRAA64.EFI" -Force
    Write-Host "  ✅ UEFI ARM64 bootloader copied" -ForegroundColor Green
} elseif ($UefiARM64Path) {
    Write-Host "  ⚠️  UEFI ARM64 bootloader not found: $UefiARM64Path" -ForegroundColor Yellow
}

# BIOS bootloader (requires special installation, just note it)
if ($BiosPath -and (Test-Path $BiosPath)) {
    Write-Host "  ℹ️  BIOS bootloader found: $BiosPath" -ForegroundColor Cyan
    Write-Host "     Note: BIOS bootloader requires special installation to BIOS Boot Partition" -ForegroundColor Yellow
    Write-Host "     This script only handles UEFI bootloaders." -ForegroundColor Yellow
}

# Verify installation
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Cyan

$allGood = $true

if (Test-Path "$espPath\EFI\BOOT\BOOTX64.EFI") {
    $size = (Get-Item "$espPath\EFI\BOOT\BOOTX64.EFI").Length
    Write-Host "  ✅ BOOTX64.EFI found ($size bytes)" -ForegroundColor Green
} else {
    Write-Host "  ❌ BOOTX64.EFI NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path "$espPath\EFI\BOOT\BOOTAA64.EFI") {
    $size = (Get-Item "$espPath\EFI\BOOT\BOOTAA64.EFI").Length
    Write-Host "  ✅ BOOTAA64.EFI found ($size bytes)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  BOOTAA64.EFI not found (optional)" -ForegroundColor Yellow
}

if ($allGood) {
    Write-Host ""
    Write-Host "✅ Bootloaders successfully installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "USB Drive is now ready for testing!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Boot locations:" -ForegroundColor Yellow
    Write-Host "  UEFI x64: $espPath\EFI\BOOT\BOOTX64.EFI" -ForegroundColor White
    if (Test-Path "$espPath\EFI\BOOT\BOOTAA64.EFI") {
        Write-Host "  UEFI ARM64: $espPath\EFI\BOOT\BOOTAA64.EFI" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "Next step: Boot from USB on target system!" -ForegroundColor Green
    Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ Installation incomplete. Please check bootloader paths." -ForegroundColor Red
    exit 1
}

