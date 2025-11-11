# Quick Start Guide
## DriveRepair by commstech v0.0.1

## Current Status

✅ **USB Structure**: Ready on drive E:
❌ **Bootloaders**: Need to be built first

## Step-by-Step Instructions

### Step 1: Build Bootloaders (On Linux)

The bootloader build is blocked on Windows, so you need to build on Linux:

```bash
# On a Linux system:
cd DriveRepair
rustup target add x86_64-unknown-uefi
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release
```

**Output location:**
```
src/boot/uefi/target/x86_64-unknown-uefi/release/drive-repair-uefi.efi
```

### Step 2: Transfer .efi File to Windows

Copy the `.efi` file from Linux to your Windows machine. For example:
- Use SCP: `scp user@linux:/path/to/drive-repair-uefi.efi .`
- Use USB drive
- Use network share
- Use cloud storage

### Step 3: Copy to USB

Once you have the `.efi` file on Windows, use the actual path:

```powershell
# Example if file is in current directory:
.\scripts\copy_bootloaders.ps1 -UsbDrive "E:" -UefiX64Path "drive-repair-uefi.efi"

# Example if file is in Downloads:
.\scripts\copy_bootloaders.ps1 -UsbDrive "E:" -UefiX64Path "C:\Users\commstech\Downloads\drive-repair-uefi.efi"

# Example if file is in project directory:
.\scripts\copy_bootloaders.ps1 -UsbDrive "E:" -UefiX64Path "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
```

### Step 4: Boot and Test

1. Insert USB into remote system
2. Boot from USB
3. Application should start!

## Alternative: Manual Copy

If you prefer to copy manually:

```powershell
# Copy to EFI boot location
Copy-Item "drive-repair-uefi.efi" "E:\EFI\BOOT\BOOTX64.EFI" -Force

# Copy to DriveRepair directory
Copy-Item "drive-repair-uefi.efi" "E:\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force
```

## What You Need Right Now

1. **Access to a Linux system** (or WSL, or VM)
2. **Build the bootloader** using the command above
3. **Get the `.efi` file** to Windows
4. **Copy it to USB** using the script

## Finding the .efi File

After building on Linux, the file will be at:
```
DriveRepair/src/boot/uefi/target/x86_64-unknown-uefi/release/drive-repair-uefi.efi
```

Copy this file to Windows, then use its path in the script.

## Summary

**Current blocker**: Need to build bootloaders on Linux first
**Once built**: Copy `.efi` file to Windows, then run copy script with actual path
**Then**: Boot from USB and test!

