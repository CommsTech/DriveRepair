# PowerShell script to create ISO file for Rufus
# DriveRepair by commstech v0.0.1
# Note: This requires oscdimg from Windows ADK or alternative tools

param(
    [Parameter(Mandatory=$false)]
    [string]$UefiX64Path = "drive-repair-uefi.efi",
    
    [Parameter(Mandatory=$false)]
    [string]$UefiARM64Path = "",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputIso = "DriveRepair.iso"
)

Write-Host "Drive Repair Tool - ISO Creation Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script creates an ISO file that can be used with Rufus." -ForegroundColor Yellow
Write-Host "However, you don't need Rufus - your USB is already set up!" -ForegroundColor Yellow
Write-Host ""

# Check if bootloader exists
if (-not (Test-Path $UefiX64Path)) {
    Write-Host "ERROR: Bootloader not found: $UefiX64Path" -ForegroundColor Red
    Write-Host ""
    Write-Host "You need to build the bootloader first:" -ForegroundColor Yellow
    Write-Host "  On Linux: cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release" -ForegroundColor White
    Write-Host "  Then copy the .efi file to this directory." -ForegroundColor White
    exit 1
}

Write-Host "Creating ISO structure..." -ForegroundColor Cyan

# Create ISO directory structure
$isoDir = "iso_temp"
if (Test-Path $isoDir) {
    Remove-Item -Path $isoDir -Recurse -Force
}
New-Item -ItemType Directory -Path "$isoDir\EFI\BOOT" -Force | Out-Null
New-Item -ItemType Directory -Path "$isoDir\EFI\DriveRepair" -Force | Out-Null

# Copy bootloaders
Write-Host "Copying bootloaders..." -ForegroundColor Yellow
Copy-Item -Path $UefiX64Path -Destination "$isoDir\EFI\BOOT\BOOTX64.EFI" -Force
Copy-Item -Path $UefiX64Path -Destination "$isoDir\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force

if ($UefiARM64Path -and (Test-Path $UefiARM64Path)) {
    Copy-Item -Path $UefiARM64Path -Destination "$isoDir\EFI\BOOT\BOOTAA64.EFI" -Force
    Copy-Item -Path $UefiARM64Path -Destination "$isoDir\EFI\DriveRepair\DRIVEREPAIRAA64.EFI" -Force
    Write-Host "  ARM64 bootloader copied" -ForegroundColor Green
}

# Create README
$readmeContent = @"
DriveRepair Bootable ISO
========================

This ISO contains the DriveRepair bootloader.

To use with Rufus:
1. Open Rufus
2. Select your USB drive
3. Click SELECT and choose this ISO file
4. Click START

Or boot directly from this ISO in a VM or on a system that supports ISO boot.

DriveRepair by commstech v0.0.1
"@
Set-Content -Path "$isoDir\README.txt" -Value $readmeContent

Write-Host "  Bootloaders copied" -ForegroundColor Green
Write-Host ""

# Check for ISO creation tools
Write-Host "Checking for ISO creation tools..." -ForegroundColor Cyan

$hasOscdimg = Get-Command oscdimg -ErrorAction SilentlyContinue
$hasMkisofs = Get-Command mkisofs -ErrorAction SilentlyContinue
$hasXorriso = Get-Command xorriso -ErrorAction SilentlyContinue

if ($hasOscdimg) {
    Write-Host "  Found: oscdimg (Windows ADK)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Creating ISO with oscdimg..." -ForegroundColor Yellow
    
    # oscdimg command for UEFI bootable ISO
    $oscdimgCmd = "oscdimg -m -o -u2 -udfver102 -bootdata:2#p0,e,b`"$isoDir\EFI\BOOT\BOOTX64.EFI`"#pEF,e,b`"$isoDir\EFI\BOOT\BOOTX64.EFI`" $isoDir $OutputIso"
    
    Write-Host "  Running: $oscdimgCmd" -ForegroundColor Cyan
    Invoke-Expression $oscdimgCmd
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputIso)) {
        Write-Host ""
        Write-Host "✅ ISO created successfully: $OutputIso" -ForegroundColor Green
        Write-Host ""
        Write-Host "You can now use this ISO with Rufus:" -ForegroundColor Cyan
        Write-Host "  1. Open Rufus" -ForegroundColor White
        Write-Host "  2. Select your USB drive" -ForegroundColor White
        Write-Host "  3. Click SELECT and choose: $OutputIso" -ForegroundColor White
        Write-Host "  4. Click START" -ForegroundColor White
    } else {
        Write-Host "  ❌ ISO creation failed" -ForegroundColor Red
    }
} elseif ($hasMkisofs) {
    Write-Host "  Found: mkisofs" -ForegroundColor Green
    Write-Host ""
    Write-Host "Creating ISO with mkisofs..." -ForegroundColor Yellow
    
    $mkisofsCmd = "mkisofs -R -J -V `"DriveRepair`" -e EFI/BOOT/BOOTX64.EFI -no-emul-boot -boot-load-size 8192 -boot-info-table -o $OutputIso $isoDir"
    
    Write-Host "  Running: $mkisofsCmd" -ForegroundColor Cyan
    Invoke-Expression $mkisofsCmd
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputIso)) {
        Write-Host ""
        Write-Host "✅ ISO created successfully: $OutputIso" -ForegroundColor Green
    } else {
        Write-Host "  ❌ ISO creation failed" -ForegroundColor Red
    }
} elseif ($hasXorriso) {
    Write-Host "  Found: xorriso" -ForegroundColor Green
    Write-Host ""
    Write-Host "Creating ISO with xorriso..." -ForegroundColor Yellow
    
    $xorrisoCmd = "xorriso -as mkisofs -R -J -V `"DriveRepair`" -e EFI/BOOT/BOOTX64.EFI -no-emul-boot -boot-load-size 8192 -boot-info-table -o $OutputIso $isoDir"
    
    Write-Host "  Running: $xorrisoCmd" -ForegroundColor Cyan
    Invoke-Expression $xorrisoCmd
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path $OutputIso)) {
        Write-Host ""
        Write-Host "✅ ISO created successfully: $OutputIso" -ForegroundColor Green
    } else {
        Write-Host "  ❌ ISO creation failed" -ForegroundColor Red
    }
} else {
    Write-Host "  ❌ No ISO creation tools found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "You need one of these tools:" -ForegroundColor Yellow
    Write-Host "  1. oscdimg (from Windows ADK)" -ForegroundColor White
    Write-Host "     Download: https://docs.microsoft.com/en-us/windows-hardware/get-started/adk-install" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  2. mkisofs or xorriso (from Cygwin or Linux)" -ForegroundColor White
    Write-Host ""
    Write-Host "OR - Skip Rufus entirely and just copy files:" -ForegroundColor Green
    Write-Host "  .\scripts\copy_bootloaders.ps1 -UsbDrive `"E:`" -UefiX64Path `"$UefiX64Path`"" -ForegroundColor White
    Write-Host ""
    Write-Host "The USB structure is already set up - you don't need Rufus!" -ForegroundColor Yellow
}

# Cleanup
if (Test-Path $isoDir) {
    Write-Host ""
    Write-Host "Cleaning up temporary files..." -ForegroundColor Cyan
    # Keep isoDir for now in case user wants to inspect it
    # Remove-Item -Path $isoDir -Recurse -Force
    Write-Host "  Temporary files kept in: $isoDir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

