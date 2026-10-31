# GATE 0 SAFETY: Destructive USB provisioning DISABLED.
Write-Host "ERROR: Destructive USB provisioning is DISABLED pending safety gates." -ForegroundColor Red
exit 2
<# DISABLED_ORIGINAL
# Build Full UEFI Bootloader
# DriveRepair by commstech v0.0.1

param(
    [string]$UsbDrive = "E:"
)

Write-Host "`n=== Building Full UEFI Bootloader ===" -ForegroundColor Cyan
Write-Host ""

# Check WSL
$wslCheck = wsl bash -c "which cargo" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cargo not found in WSL. Please install Rust:" -ForegroundColor Red
    Write-Host "  wsl" -ForegroundColor White
    Write-Host "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh" -ForegroundColor White
    exit 1
}

Write-Host "Step 1: Building bootloader..." -ForegroundColor Yellow

$projectPath = (Get-Location).Path
$wslPath = $projectPath -replace '^([A-Z]):', '/mnt/$1' -replace '\\', '/'
$wslPath = $wslPath.ToLower()

$buildScript = @"
#!/bin/bash
set -e
source ~/.cargo/env 2>/dev/null || true
cd '$wslPath'
export CARGO_TARGET_DIR=src/boot/uefi/target
rustup target add x86_64-unknown-uefi 2>/dev/null || true
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release
"@

$scriptFile = "$env:TEMP\build_uefi_$(Get-Date -Format 'yyyyMMddHHmmss').sh"
$buildScript | Out-File -FilePath $scriptFile -Encoding ASCII -NoNewline

Write-Host "  Running build in WSL..." -ForegroundColor Gray
$buildOutput = wsl bash $scriptFile 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Build successful!" -ForegroundColor Green
    
    $efiPath = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
    if (Test-Path $efiPath) {
        $size = (Get-Item $efiPath).Length / 1KB
        Write-Host "  Bootloader size: $([math]::Round($size, 2)) KB" -ForegroundColor Cyan
        
        Write-Host "`nStep 2: Copying to USB..." -ForegroundColor Yellow
        Write-Host "  USB Drive: $UsbDrive" -ForegroundColor Gray
        
        try {
            Copy-Item $efiPath "$UsbDrive\EFI\BOOT\BOOTX64.EFI" -Force
            Copy-Item $efiPath "$UsbDrive\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force
            Write-Host "  ✅ Copied successfully!" -ForegroundColor Green
            Write-Host "`n✅ USB drive is ready for testing!" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠️  Copy failed. Please run as Administrator:" -ForegroundColor Yellow
            Write-Host "    Copy-Item `"$efiPath`" `"$UsbDrive\EFI\BOOT\BOOTX64.EFI`" -Force" -ForegroundColor White
            Write-Host "    Copy-Item `"$efiPath`" `"$UsbDrive\EFI\DriveRepair\DRIVEREPAIRX64.EFI`" -Force" -ForegroundColor White
        }
    } else {
        Write-Host "  ❌ Bootloader file not found at: $efiPath" -ForegroundColor Red
    }
} else {
    Write-Host "  ❌ Build failed!" -ForegroundColor Red
    Write-Host "`nBuild errors:" -ForegroundColor Yellow
    $buildOutput | Select-String -Pattern "error\[" | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "`nFull output saved for debugging." -ForegroundColor Gray
}

Remove-Item $scriptFile -ErrorAction SilentlyContinue


#>
