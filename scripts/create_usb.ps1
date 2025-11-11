# PowerShell script to create bootable USB drive
# Creates hybrid UEFI/BIOS bootable USB with GPT partition table

param(
    [Parameter(Mandatory=$false)]
    [string]$UsbDrive = "F:",
    
    [Parameter(Mandatory=$false)]
    [string]$UefiBootloaderX64 = "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi",
    
    [Parameter(Mandatory=$false)]
    [string]$UefiBootloaderARM64 = "src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi",
    
    [Parameter(Mandatory=$false)]
    [string]$BiosBootloader = "src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios"
)

Write-Host "Drive Repair Tool - USB Creation Script" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Validate USB drive
if (-not (Test-Path $UsbDrive)) {
    Write-Host "ERROR: USB drive not found: $UsbDrive" -ForegroundColor Red
    exit 1
}

# Get disk number from drive letter
$diskNumber = (Get-Partition -DriveLetter $UsbDrive[0]).DiskNumber
$disk = Get-Disk -Number $diskNumber

Write-Host "Target USB Drive:" -ForegroundColor Yellow
Write-Host "  Drive Letter: $UsbDrive"
Write-Host "  Disk Number: $diskNumber"
Write-Host "  Size: $($disk.Size / 1GB) GB"
Write-Host ""

# Confirm before proceeding
$confirm = Read-Host "WARNING: This will erase all data on the USB drive. Continue? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Operation cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Creating bootable USB drive..." -ForegroundColor Green

# Step 1: Clean the disk and convert to GPT
Write-Host "Step 1: Cleaning disk and converting to GPT..." -ForegroundColor Cyan
# Check current partition style
$currentStyle = (Get-Disk -Number $diskNumber).PartitionStyle
Write-Host "  Current partition style: $currentStyle" -ForegroundColor Yellow

if ($currentStyle -eq "MBR") {
    Write-Host "  Converting MBR to GPT..." -ForegroundColor Yellow
    # Remove all partitions first
    $partitions = Get-Partition -DiskNumber $diskNumber -ErrorAction SilentlyContinue
    if ($partitions) {
        foreach ($partition in $partitions) {
            Remove-Partition -InputObject $partition -Confirm:$false -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
    # Clear the disk completely - this removes all data and partitions
    Clear-Disk -Number $diskNumber -RemoveData -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    # Use diskpart to convert MBR to GPT (more reliable)
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
    # Remove all partitions
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

# Step 3: Create EFI System Partition (ESP)
Write-Host "Step 3: Creating EFI System Partition..." -ForegroundColor Cyan
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

# Step 4: Create BIOS Boot Partition (for legacy boot)
Write-Host "Step 4: Creating BIOS Boot Partition..." -ForegroundColor Cyan
$biosSize = 1MB
try {
    $bios = New-Partition -DiskNumber $diskNumber -Size $biosSize -GptType '{21686148-6449-6e6f-744e-656564454649}' -ErrorAction Stop
    Write-Host "  BIOS Boot Partition created" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Failed to create BIOS Boot Partition: $_" -ForegroundColor Yellow
    Write-Host "  Continuing without BIOS boot partition..." -ForegroundColor Yellow
    $bios = $null
}

# Step 5: Create data partition (optional, for logs/reports)
Write-Host "Step 5: Creating data partition..." -ForegroundColor Cyan
$biosSizeUsed = if ($bios) { $biosSize } else { 0 }
$dataSize = $disk.Size - $espSize - $biosSizeUsed
try {
    $data = New-Partition -DiskNumber $diskNumber -Size $dataSize -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}' -AssignDriveLetter -ErrorAction Stop
    Start-Sleep -Seconds 1
    Format-Volume -Partition $data -FileSystem NTFS -NewFileSystemLabel "DriveRepair" -Confirm:$false
    Write-Host "  Data partition created" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Failed to create data partition: $_" -ForegroundColor Yellow
    Write-Host "  Continuing without data partition..." -ForegroundColor Yellow
    $data = $null
}

# Step 6: Copy bootloaders
Write-Host "Step 6: Copying bootloaders..." -ForegroundColor Cyan

# Get ESP drive letter
$espPartition = Get-Partition -DiskNumber $diskNumber | Where-Object { $_.GptType -eq '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' } | Select-Object -First 1
if (-not $espPartition -or -not $espPartition.DriveLetter) {
    Write-Host "  ERROR: Could not find EFI System Partition with drive letter" -ForegroundColor Red
    exit 1
}
$espDrive = $espPartition.DriveLetter
$espPath = "$($espDrive):"

# Create EFI directory structure
New-Item -ItemType Directory -Path "$espPath\EFI\BOOT" -Force | Out-Null
New-Item -ItemType Directory -Path "$espPath\EFI\DriveRepair" -Force | Out-Null

# Copy UEFI bootloaders (x64 and ARM64)
if (Test-Path $UefiBootloaderX64) {
    Copy-Item -Path $UefiBootloaderX64 -Destination "$espPath\EFI\BOOT\BOOTX64.EFI" -Force
    Copy-Item -Path $UefiBootloaderX64 -Destination "$espPath\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force
    Write-Host "  UEFI x64 bootloader copied" -ForegroundColor Green
} else {
    Write-Host "  WARNING: UEFI x64 bootloader not found: $UefiBootloaderX64" -ForegroundColor Yellow
}

if (Test-Path $UefiBootloaderARM64) {
    Copy-Item -Path $UefiBootloaderARM64 -Destination "$espPath\EFI\BOOT\BOOTAA64.EFI" -Force
    Copy-Item -Path $UefiBootloaderARM64 -Destination "$espPath\EFI\DriveRepair\DRIVEREPAIRAA64.EFI" -Force
    Write-Host "  UEFI ARM64 bootloader copied" -ForegroundColor Green
} else {
    Write-Host "  WARNING: UEFI ARM64 bootloader not found: $UefiBootloaderARM64" -ForegroundColor Yellow
}

# Copy BIOS bootloader (if available)
if (Test-Path $BiosBootloader) {
    # TODO: Install BIOS bootloader to BIOS Boot Partition
    # This requires writing to the partition directly
    Write-Host "  BIOS bootloader found (manual installation may be required)" -ForegroundColor Yellow
} else {
    Write-Host "  WARNING: BIOS bootloader not found: $BiosBootloader" -ForegroundColor Yellow
}

# Step 7: Create boot configuration
Write-Host "Step 7: Creating boot configuration..." -ForegroundColor Cyan
$configContent = @"
# Drive Repair Tool Configuration
# Bootable USB created on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@
Set-Content -Path "$espPath\EFI\DriveRepair\config.txt" -Value $configContent

# Step 8: Verify installation
Write-Host "Step 8: Verifying installation..." -ForegroundColor Cyan
if (Test-Path "$espPath\EFI\BOOT\BOOTX64.EFI") {
    Write-Host "  UEFI x64 bootloader verified" -ForegroundColor Green
} else {
    Write-Host "  WARNING: UEFI x64 bootloader not found" -ForegroundColor Yellow
}
if (Test-Path "$espPath\EFI\BOOT\BOOTAA64.EFI") {
    Write-Host "  UEFI ARM64 bootloader verified" -ForegroundColor Green
} else {
    Write-Host "  WARNING: UEFI ARM64 bootloader not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Bootable USB drive created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "USB Drive Layout:" -ForegroundColor Yellow
Write-Host "  EFI System Partition: $espPath (FAT32)"
if ($bios) {
    Write-Host "  BIOS Boot Partition: (hidden)"
} else {
    Write-Host "  BIOS Boot Partition: (not created)"
}
$dataPartition = Get-Partition -DiskNumber $diskNumber | Where-Object { $_.GptType -eq '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}' } | Select-Object -First 1
if ($dataPartition -and $dataPartition.DriveLetter) {
    Write-Host "  Data Partition: $($dataPartition.DriveLetter): (NTFS)"
} else {
    Write-Host "  Data Partition: (not created)"
}
Write-Host ""
Write-Host "Boot Methods:" -ForegroundColor Yellow
Write-Host "  UEFI x64: Boot from EFI System Partition (BOOTX64.EFI)"
Write-Host "  UEFI ARM64: Boot from EFI System Partition (BOOTAA64.EFI)"
Write-Host "  BIOS: Boot from BIOS Boot Partition (if configured)"
Write-Host ""
Write-Host "Note: You may need to configure your system's boot order to boot from USB." -ForegroundColor Cyan
Write-Host "DriveRepair by commstech v0.0.1" -ForegroundColor Cyan

