# PowerShell script to build bootloaders and install to USB drive
# Combines build and USB installation steps

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false
)

Write-Host "Drive Repair Tool - Build and Install Script" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build bootloaders (unless skipped)
if (-not $SkipBuild) {
    Write-Host "Step 1: Building bootloaders..." -ForegroundColor Cyan
    Write-Host ""
    
    # Check if cargo is available
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: cargo not found. Please install Rust." -ForegroundColor Red
        Write-Host "Download from: https://rustup.rs/" -ForegroundColor Yellow
        exit 1
    }
    
    # Check and install targets
    Write-Host "Checking Rust targets..." -ForegroundColor Yellow
    $targets = rustup target list --installed
    $neededTargets = @("x86_64-unknown-uefi", "aarch64-unknown-uefi", "x86_64-unknown-none")
    $missingTargets = @()
    
    foreach ($target in $neededTargets) {
        if ($targets -notcontains $target) {
            $missingTargets += $target
            Write-Host "  Installing: $target" -ForegroundColor Yellow
            rustup target add $target
        } else {
            Write-Host "  Installed: $target" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "Building UEFI x64 bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  UEFI x64 build successful" -ForegroundColor Green
    } else {
        Write-Host "  UEFI x64 build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Building UEFI ARM64 bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\uefi\Cargo.toml --target aarch64-unknown-uefi --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  UEFI ARM64 build successful" -ForegroundColor Green
    } else {
        Write-Host "  UEFI ARM64 build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Building BIOS bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\bios\Cargo.toml --target x86_64-unknown-none --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  BIOS build successful" -ForegroundColor Green
    } else {
        Write-Host "  BIOS build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
} else {
    Write-Host "Step 1: Skipping build (using existing bootloaders)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 2: Find bootloader files
Write-Host "Step 2: Locating bootloader files..." -ForegroundColor Cyan

$uefiX64Path = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
$uefiARM64Path = "src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi"
$biosPath = "src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios"

$bootloadersFound = $true

if (-not (Test-Path $uefiX64Path)) {
    Write-Host "  ERROR: UEFI x64 bootloader not found: $uefiX64Path" -ForegroundColor Red
    $bootloadersFound = $false
} else {
    Write-Host "  UEFI x64: Found" -ForegroundColor Green
}

if (-not (Test-Path $uefiARM64Path)) {
    Write-Host "  ERROR: UEFI ARM64 bootloader not found: $uefiARM64Path" -ForegroundColor Red
    $bootloadersFound = $false
} else {
    Write-Host "  UEFI ARM64: Found" -ForegroundColor Green
}

if (-not (Test-Path $biosPath)) {
    Write-Host "  WARNING: BIOS bootloader not found: $biosPath" -ForegroundColor Yellow
} else {
    Write-Host "  BIOS: Found" -ForegroundColor Green
}

if (-not $bootloadersFound) {
    Write-Host ""
    Write-Host "ERROR: Required bootloaders not found. Please build first." -ForegroundColor Red
    Write-Host "Run: .\scripts\build_bootloaders.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 3: Verify USB drive
Write-Host "Step 3: Verifying USB drive..." -ForegroundColor Cyan

$driveLetter = $UsbDrive.TrimEnd('\', ':')
$espPath = "$driveLetter`:\"

if (-not (Test-Path $espPath)) {
    Write-Host "  ERROR: USB drive not found: $espPath" -ForegroundColor Red
    Write-Host "  Please create USB drive first: .\scripts\create_usb.ps1 -UsbDrive `"$UsbDrive`"" -ForegroundColor Yellow
    exit 1
}

# Check if EFI directory exists
$efiBootPath = "$espPath\EFI\BOOT"
if (-not (Test-Path $efiBootPath)) {
    Write-Host "  WARNING: EFI\BOOT directory not found. Creating..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $efiBootPath -Force | Out-Null
}

$efiDriveRepairPath = "$espPath\EFI\DriveRepair"
if (-not (Test-Path $efiDriveRepairPath)) {
    Write-Host "  WARNING: EFI\DriveRepair directory not found. Creating..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $efiDriveRepairPath -Force | Out-Null
}

Write-Host "  USB drive verified: $espPath" -ForegroundColor Green
Write-Host ""

# Step 4: Copy bootloaders
Write-Host "Step 4: Copying bootloaders to USB drive..." -ForegroundColor Cyan

# Copy UEFI x64
if (Test-Path $uefiX64Path) {
    Copy-Item -Path $uefiX64Path -Destination "$efiBootPath\BOOTX64.EFI" -Force
    Copy-Item -Path $uefiX64Path -Destination "$efiDriveRepairPath\DRIVEREPAIRX64.EFI" -Force
    Write-Host "  UEFI x64 bootloader copied" -ForegroundColor Green
}

# Copy UEFI ARM64
if (Test-Path $uefiARM64Path) {
    Copy-Item -Path $uefiARM64Path -Destination "$efiBootPath\BOOTAA64.EFI" -Force
    Copy-Item -Path $uefiARM64Path -Destination "$efiDriveRepairPath\DRIVEREPAIRAA64.EFI" -Force
    Write-Host "  UEFI ARM64 bootloader copied" -ForegroundColor Green
}

# BIOS bootloader (note: requires special installation to BIOS Boot Partition)
if (Test-Path $biosPath) {
    Write-Host "  BIOS bootloader found (manual installation may be required)" -ForegroundColor Yellow
    Write-Host "  BIOS bootloader location: $biosPath" -ForegroundColor Cyan
}

Write-Host ""

# Step 5: Verify installation
Write-Host "Step 5: Verifying installation..." -ForegroundColor Cyan

$allGood = $true

if (Test-Path "$efiBootPath\BOOTX64.EFI") {
    Write-Host "  UEFI x64: Verified" -ForegroundColor Green
} else {
    Write-Host "  UEFI x64: NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path "$efiBootPath\BOOTAA64.EFI") {
    Write-Host "  UEFI ARM64: Verified" -ForegroundColor Green
} else {
    Write-Host "  UEFI ARM64: NOT FOUND" -ForegroundColor Red
    $allGood = $false
}

if ($allGood) {
    Write-Host ""
    Write-Host "Bootloaders successfully installed to USB drive!" -ForegroundColor Green
    Write-Host ""
    Write-Host "USB Drive: $espPath" -ForegroundColor Cyan
    Write-Host "  UEFI x64: $efiBootPath\BOOTX64.EFI" -ForegroundColor White
    Write-Host "  UEFI ARM64: $efiBootPath\BOOTAA64.EFI" -ForegroundColor White
    Write-Host ""
    Write-Host "Ready for testing!" -ForegroundColor Green
    Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "ERROR: Installation verification failed" -ForegroundColor Red
    exit 1
}

