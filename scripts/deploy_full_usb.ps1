# =============================================================================
# GATE 0 SAFETY: Destructive USB provisioning is DISABLED pending safety gates.
# This script will NOT erase disks, format media, or write bootloaders.
# Original body preserved below but is unreachable.
# =============================================================================
Write-Host "ERROR: Destructive USB provisioning is DISABLED pending Gate 0 safety gates." -ForegroundColor Red
Write-Host "Refusing to touch USB/disk media. Exit code 2." -ForegroundColor Red
exit 2

<# DISABLED_ORIGINAL_BODY
# Build and deploy full UEFI bootloader to USB drive
param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive
)

Write-Host "Building full UEFI bootloader..." -ForegroundColor Cyan
$buildOutput = wsl bash -c "cd /mnt/c/Users/commstech/Github/DriveRepair && source ~/.cargo/env && timeout 180 cargo build --manifest-path src/boot/uefi/Cargo.toml --bin drive-repair-uefi --target x86_64-unknown-uefi --release 2>&1"

if ($buildOutput -match "Finished.*successfully") {
    Write-Host "Build successful!" -ForegroundColor Green
    
    $efiPath = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
    if (Test-Path $efiPath) {
        Write-Host "Copying to USB drive $UsbDrive..." -ForegroundColor Yellow
        Copy-Item $efiPath "$UsbDrive\EFI\BOOT\BOOTX64.EFI" -Force
        Copy-Item $efiPath "$UsbDrive\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force
        Write-Host "Done! USB drive is ready." -ForegroundColor Green
    } else {
        Write-Host "Bootloader not found at: $efiPath" -ForegroundColor Red
    }
} else {
    Write-Host "Build failed. Errors:" -ForegroundColor Red
    $buildOutput | Select-String -Pattern "error\[" | Select-Object -First 10
}

#>
