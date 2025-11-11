# PowerShell script to set up USB drive structure only (without building bootloaders)
# DriveRepair by commstech v0.0.1
# Use this if you want to manually copy bootloaders later or use Rufus

param(
    [Parameter(Mandatory=$true)]
    [string]$UsbDrive
)

Write-Host "Drive Repair Tool - USB Structure Setup Only" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "  1. Set up GPT partition table" -ForegroundColor White
Write-Host "  2. Create EFI System Partition (FAT32)" -ForegroundColor White
Write-Host "  3. Create BIOS Boot Partition" -ForegroundColor White
Write-Host "  4. Create EFI directory structure" -ForegroundColor White
Write-Host ""
Write-Host "Bootloaders can be copied manually later." -ForegroundColor Cyan
Write-Host ""

# Validate drive
$driveLetter = $UsbDrive.TrimEnd('\', ':')
$disk = Get-Disk | Where-Object { $_.PartitionStyle -ne $null -and (Get-Partition -DiskNumber $_.Number -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter -eq $driveLetter }) } | Select-Object -First 1

if (-not $disk) {
    Write-Host "ERROR: Could not find disk for drive $driveLetter" -ForegroundColor Red
    exit 1
}

$diskNumber = $disk.Number

Write-Host "Target USB Drive:" -ForegroundColor Cyan
Write-Host "  Drive Letter: $driveLetter`:" -ForegroundColor White
Write-Host "  Disk Number: $diskNumber" -ForegroundColor White
Write-Host "  Size: $($disk.Size / 1GB) GB" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "WARNING: This will erase all data on the USB drive. Continue? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Setting up USB drive structure..." -ForegroundColor Green

# Step 1: Clean and convert to GPT
Write-Host "Step 1: Cleaning disk and converting to GPT..." -ForegroundColor Cyan
$currentStyle = (Get-Disk -Number $diskNumber).PartitionStyle
Write-Host "  Current partition style: $currentStyle" -ForegroundColor Yellow

if ($currentStyle -eq "MBR") {
    Write-Host "  Converting MBR to GPT..." -ForegroundColor Yellow
    $partitions = Get-Partition -DiskNumber $diskNumber -ErrorAction SilentlyContinue
    if ($partitions) {
        foreach ($partition in $partitions) {
            Remove-Partition -InputObject $partition -Confirm:$false -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
    Clear-Disk -Number $diskNumber -RemoveData -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $diskpartScript = @"
select disk $diskNumber
clean
convert gpt
exit
"@
    $diskpartScript | diskpart | Out-Null
    Start-Sleep -Seconds 1
    Write-Host "  Disk converted to GPT" -ForegroundColor Green
} elseif ($currentStyle -eq "GPT") {
    Write-Host "  Disk is already GPT, cleaning partitions..." -ForegroundColor Yellow
    $partitions = Get-Partition -DiskNumber $diskNumber -ErrorAction SilentlyContinue
    if ($partitions) {
        foreach ($partition in $partitions) {
            Remove-Partition -InputObject $partition -Confirm:$false -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "  Disk cleaned" -ForegroundColor Green
} else {
    Write-Host "  Disk is raw, initializing as GPT..." -ForegroundColor Yellow
    Initialize-Disk -Number $diskNumber -PartitionStyle GPT -Confirm:$false
    Write-Host "  Disk initialized as GPT" -ForegroundColor Green
}

# Step 2: Create EFI System Partition
Write-Host "Step 2: Creating EFI System Partition..." -ForegroundColor Cyan
$espSize = 100MB
try {
    $esp = New-Partition -DiskNumber $diskNumber -Size $espSize -GptType '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' -AssignDriveLetter -ErrorAction Stop
    Start-Sleep -Seconds 1
    Format-Volume -Partition $esp -FileSystem FAT32 -NewFileSystemLabel "EFI" -Confirm:$false
    Write-Host "  EFI System Partition created" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Failed to create EFI System Partition: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Create BIOS Boot Partition
Write-Host "Step 3: Creating BIOS Boot Partition..." -ForegroundColor Cyan
$biosSize = 1MB
try {
    $bios = New-Partition -DiskNumber $diskNumber -Size $biosSize -GptType '{21686148-6449-6e6f-744e-656564454649}' -ErrorAction Stop
    Write-Host "  BIOS Boot Partition created" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Failed to create BIOS Boot Partition: $_" -ForegroundColor Yellow
    Write-Host "  Continuing without BIOS boot partition..." -ForegroundColor Yellow
}

# Step 4: Create EFI directory structure
Write-Host "Step 4: Creating EFI directory structure..." -ForegroundColor Cyan
$espPartition = Get-Partition -DiskNumber $diskNumber | Where-Object { $_.GptType -eq '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' } | Select-Object -First 1
if (-not $espPartition -or -not $espPartition.DriveLetter) {
    Write-Host "  ERROR: Could not find EFI System Partition with drive letter" -ForegroundColor Red
    exit 1
}
$espDrive = $espPartition.DriveLetter
$espPath = "$($espDrive):"

New-Item -ItemType Directory -Path "$espPath\EFI\BOOT" -Force | Out-Null
New-Item -ItemType Directory -Path "$espPath\EFI\DriveRepair" -Force | Out-Null
Write-Host "  EFI directory structure created" -ForegroundColor Green

# Step 5: Create README
Write-Host "Step 5: Creating README..." -ForegroundColor Cyan
$readmeContent = @"
DriveRepair Bootable USB
========================

This USB drive is set up for UEFI boot.

To complete setup:
1. Build the bootloaders (when Rust target issue is resolved):
   cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
   cargo build --manifest-path src\boot\uefi\Cargo.toml --target aarch64-unknown-uefi --release

2. Copy bootloaders to:
   - $espPath\EFI\BOOT\BOOTX64.EFI (for x64 UEFI)
   - $espPath\EFI\BOOT\BOOTAA64.EFI (for ARM64 UEFI)
   - $espPath\EFI\DriveRepair\DRIVEREPAIRX64.EFI
   - $espPath\EFI\DriveRepair\DRIVEREPAIRAA64.EFI

3. Boot from USB in UEFI mode

DriveRepair by commstech v0.0.1
"@
Set-Content -Path "$espPath\EFI\DriveRepair\README.txt" -Value $readmeContent
Write-Host "  README created" -ForegroundColor Green

Write-Host ""
Write-Host "USB drive structure setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "EFI System Partition: $espPath" -ForegroundColor Cyan
Write-Host "  Directory structure ready for bootloaders" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Fix Rust UEFI target issue (see MANUAL_FIX.md)" -ForegroundColor White
Write-Host "  2. Build bootloaders" -ForegroundColor White
Write-Host "  3. Copy .efi files to $espPath\EFI\BOOT\" -ForegroundColor White
Write-Host ""
Write-Host "Or use Rufus to create bootable USB from ISO (if you create one)" -ForegroundColor Cyan

