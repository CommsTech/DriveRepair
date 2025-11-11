# PowerShell script to build all bootloaders
# Builds UEFI (x64 and ARM64) and BIOS bootloaders

param(
    [Parameter(Mandatory=$false)]
    [switch]$SkipUefiX64 = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipUefiARM64 = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBios = $false
)

Write-Host "Drive Repair Tool - Bootloader Build Script" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Check if cargo is available
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: cargo not found. Please install Rust." -ForegroundColor Red
    exit 1
}

# Check if targets are installed
Write-Host "Checking Rust targets..." -ForegroundColor Cyan
$targets = rustup target list --installed
$neededTargets = @("x86_64-unknown-uefi", "aarch64-unknown-uefi", "x86_64-unknown-none")
$missingTargets = @()

foreach ($target in $neededTargets) {
    if ($targets -notcontains $target) {
        $missingTargets += $target
        Write-Host "  Missing: $target" -ForegroundColor Yellow
    } else {
        Write-Host "  Installed: $target" -ForegroundColor Green
    }
}

if ($missingTargets.Count -gt 0) {
    Write-Host ""
    Write-Host "Installing missing targets..." -ForegroundColor Cyan
    foreach ($target in $missingTargets) {
        rustup target add $target
    }
}

Write-Host ""
Write-Host "Building bootloaders..." -ForegroundColor Cyan
Write-Host ""

# Build UEFI x64
if (-not $SkipUefiX64) {
    Write-Host "Building UEFI x64 bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  UEFI x64 build successful" -ForegroundColor Green
    } else {
        Write-Host "  UEFI x64 build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Build UEFI ARM64
if (-not $SkipUefiARM64) {
    Write-Host "Building UEFI ARM64 bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\uefi\Cargo.toml --target aarch64-unknown-uefi --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  UEFI ARM64 build successful" -ForegroundColor Green
    } else {
        Write-Host "  UEFI ARM64 build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Build BIOS
if (-not $SkipBios) {
    Write-Host "Building BIOS bootloader..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\bios\Cargo.toml --target x86_64-unknown-none --release
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  BIOS build successful" -ForegroundColor Green
    } else {
        Write-Host "  BIOS build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Check build results
Write-Host "Build Results:" -ForegroundColor Cyan
$uefiX64 = Get-ChildItem -Path "src\boot\uefi\target" -Recurse -Filter "drive-repair-uefi.efi" -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -like "*x86_64*" } | Select-Object -First 1
$uefiARM64 = Get-ChildItem -Path "src\boot\uefi\target" -Recurse -Filter "drive-repair-uefi.efi" -ErrorAction SilentlyContinue | Where-Object { $_.DirectoryName -like "*aarch64*" } | Select-Object -First 1
$bios = Get-ChildItem -Path "src\boot\bios\target" -Recurse -Filter "drive-repair-bios*" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "*.d" -and $_.Name -notlike "*.rmeta" } | Select-Object -First 1

if ($uefiX64) {
    Write-Host "  UEFI x64: $($uefiX64.FullName)" -ForegroundColor Green
} else {
    Write-Host "  UEFI x64: NOT FOUND" -ForegroundColor Red
}

if ($uefiARM64) {
    Write-Host "  UEFI ARM64: $($uefiARM64.FullName)" -ForegroundColor Green
} else {
    Write-Host "  UEFI ARM64: NOT FOUND" -ForegroundColor Red
}

if ($bios) {
    Write-Host "  BIOS: $($bios.FullName)" -ForegroundColor Green
} else {
    Write-Host "  BIOS: NOT FOUND" -ForegroundColor Red
}

Write-Host ""
Write-Host "Build process complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step: Run USB creation script as Administrator:" -ForegroundColor Yellow
Write-Host "  .\scripts\create_usb.ps1 -UsbDrive `"F:`"" -ForegroundColor White

