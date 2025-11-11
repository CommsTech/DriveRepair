# Build minimal UEFI bootloader (no library dependencies)
# DriveRepair by commstech v0.0.1

param(
    [Parameter(Mandatory=$false)]
    [switch]$UseWsl = $true
)

Write-Host "Drive Repair Tool - Minimal Bootloader Builder" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Check if WSL is available
if ($UseWsl) {
    $wslAvailable = Get-Command wsl -ErrorAction SilentlyContinue
    if (-not $wslAvailable) {
        Write-Host "ERROR: WSL is not installed!" -ForegroundColor Red
        Write-Host "Install WSL with: wsl --install" -ForegroundColor Yellow
        exit 1
    }
}

$projectPath = (Get-Location).Path
$wslPath = $projectPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslPath = $wslPath.ToLower()

Write-Host "Building minimal UEFI bootloader..." -ForegroundColor Yellow
Write-Host ""

if ($UseWsl) {
    Write-Host "Building in WSL..." -ForegroundColor Yellow
    
    # Check if Cargo_minimal.toml exists, create if not
    $minimalCargoPath = "src\boot\uefi\Cargo_minimal.toml"
    if (-not (Test-Path $minimalCargoPath)) {
        Write-Host "  Creating Cargo_minimal.toml..." -ForegroundColor Yellow
        # File should already exist from the write above
    }
    
    $buildCmd = @"
cd '$wslPath/src/boot/uefi' && \
source ~/.cargo/env 2>/dev/null || true && \
rustup target add x86_64-unknown-uefi && \
cargo build --bin drive-repair-uefi-minimal --target x86_64-unknown-uefi --release
"@
    
    wsl bash -c $buildCmd
    
    if ($LASTEXITCODE -eq 0) {
        $efiPath = "$projectPath\src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi-minimal.efi"
        if (Test-Path $efiPath) {
            Write-Host "  ✅ Minimal bootloader built successfully!" -ForegroundColor Green
            Write-Host "  File: $efiPath" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "You can now copy this to your USB:" -ForegroundColor Yellow
            Write-Host "  Copy-Item `"$efiPath`" `"E:\EFI\BOOT\BOOTX64.EFI`" -Force" -ForegroundColor White
        } else {
            Write-Host "  ⚠️  Build completed but file not found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ Build failed" -ForegroundColor Red
    }
} else {
    Write-Host "Building natively..." -ForegroundColor Yellow
    cargo build --manifest-path src\boot\uefi\Cargo_minimal.toml --target x86_64-unknown-uefi --release
}

Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

