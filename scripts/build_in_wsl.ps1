# PowerShell script to build bootloaders using WSL
# DriveRepair by commstech v0.0.1

param(
    [Parameter(Mandatory=$false)]
    [switch]$SkipUefiX64 = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipUefiARM64 = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBios = $false
)

Write-Host "Drive Repair Tool - WSL Build Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if WSL is available
$wslAvailable = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslAvailable) {
    Write-Host "ERROR: WSL is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install WSL with:" -ForegroundColor Yellow
    Write-Host "  wsl --install" -ForegroundColor White
    Write-Host "  (Run PowerShell as Administrator)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or install a specific distribution:" -ForegroundColor Yellow
    Write-Host "  wsl --install -d Ubuntu" -ForegroundColor White
    exit 1
}

Write-Host "WSL found! Building bootloaders in WSL..." -ForegroundColor Green
Write-Host ""

# Get current directory (Windows path)
$projectPath = (Get-Location).Path
$wslPath = $projectPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslPath = $wslPath.ToLower()

Write-Host "Project path (Windows): $projectPath" -ForegroundColor Cyan
Write-Host "Project path (WSL):     $wslPath" -ForegroundColor Cyan
Write-Host ""

# Check if Rust is installed in WSL
Write-Host "Checking Rust installation in WSL..." -ForegroundColor Yellow
$rustCheck = wsl bash -c "command -v rustc > /dev/null 2>&1 && echo 'installed' || echo 'not_installed'"
if ($rustCheck -eq "not_installed") {
    Write-Host "  Rust not found in WSL. Installing..." -ForegroundColor Yellow
    wsl bash -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
    wsl bash -c "source ~/.cargo/env && rustup default stable"
    Write-Host "  Rust installed!" -ForegroundColor Green
} else {
    Write-Host "  Rust found in WSL" -ForegroundColor Green
}

Write-Host ""

# Build UEFI x64
if (-not $SkipUefiX64) {
    Write-Host "Building UEFI x64 bootloader in WSL..." -ForegroundColor Yellow
    
    $buildCmd = @"
cd '$wslPath' && \
source ~/.cargo/env 2>/dev/null || true && \
rustup target add x86_64-unknown-uefi && \
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release
"@
    
    wsl bash -c $buildCmd
    
    if ($LASTEXITCODE -eq 0) {
        $efiPath = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
        if (Test-Path $efiPath) {
            Write-Host "  ✅ UEFI x64 build successful!" -ForegroundColor Green
            Write-Host "  File: $efiPath" -ForegroundColor Cyan
        } else {
            Write-Host "  ⚠️  Build completed but file not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ UEFI x64 build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Build UEFI ARM64
if (-not $SkipUefiARM64) {
    Write-Host "Building UEFI ARM64 bootloader in WSL..." -ForegroundColor Yellow
    
    $buildCmd = @"
cd '$wslPath' && \
source ~/.cargo/env 2>/dev/null || true && \
rustup target add aarch64-unknown-uefi && \
cargo build --manifest-path src/boot/uefi/Cargo.toml --target aarch64-unknown-uefi --release
"@
    
    wsl bash -c $buildCmd
    
    if ($LASTEXITCODE -eq 0) {
        $efiPath = "$projectPath\src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi"
        if (Test-Path $efiPath) {
            Write-Host "  ✅ UEFI ARM64 build successful!" -ForegroundColor Green
            Write-Host "  File: $efiPath" -ForegroundColor Cyan
        } else {
            Write-Host "  ⚠️  Build completed but file not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ UEFI ARM64 build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Build BIOS
if (-not $SkipBios) {
    Write-Host "Building BIOS bootloader in WSL..." -ForegroundColor Yellow
    
    $buildCmd = @"
cd '$wslPath' && \
source ~/.cargo/env 2>/dev/null || true && \
rustup target add x86_64-unknown-none && \
cargo build --manifest-path src/boot/bios/Cargo.toml --target x86_64-unknown-none --release
"@
    
    wsl bash -c $buildCmd
    
    if ($LASTEXITCODE -eq 0) {
        $biosPath = "$projectPath\src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios"
        if (Test-Path $biosPath) {
            Write-Host "  ✅ BIOS build successful!" -ForegroundColor Green
            Write-Host "  File: $biosPath" -ForegroundColor Cyan
        } else {
            Write-Host "  ⚠️  Build completed but file not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ BIOS build failed" -ForegroundColor Red
    }
    Write-Host ""
}

# Summary
Write-Host "Build Summary:" -ForegroundColor Cyan
$uefiX64 = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
$uefiARM64 = "$projectPath\src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi"
$bios = "$projectPath\src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios"

if (Test-Path $uefiX64) {
    Write-Host "  ✅ UEFI x64: $uefiX64" -ForegroundColor Green
} else {
    Write-Host "  ❌ UEFI x64: NOT FOUND" -ForegroundColor Red
}

if (Test-Path $uefiARM64) {
    Write-Host "  ✅ UEFI ARM64: $uefiARM64" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  UEFI ARM64: NOT FOUND (optional)" -ForegroundColor Yellow
}

if (Test-Path $bios) {
    Write-Host "  ✅ BIOS: $bios" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  BIOS: NOT FOUND (optional)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next step: Copy bootloaders to USB" -ForegroundColor Cyan
if (Test-Path $uefiX64) {
    Write-Host "  .\scripts\copy_bootloaders.ps1 -UsbDrive `"E:`" -UefiX64Path `"$uefiX64`"" -ForegroundColor White
}
Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

