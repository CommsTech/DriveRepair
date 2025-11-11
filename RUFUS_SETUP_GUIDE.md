# Rufus Setup Guide for DriveRepair
## DriveRepair by commstech v0.0.1

## Important: You Still Need Bootloaders First!

**The USB structure is ready, but you need the `.efi` bootloader files to run the application.**

## Two Approaches

### Option 1: Direct Copy (Simpler - Recommended)

Since the USB structure is already set up, you just need to copy the `.efi` files:

1. **Get the bootloaders** (build on Linux or use pre-built):
   - `drive-repair-uefi.efi` (x64 version)
   - `drive-repair-uefi.efi` (ARM64 version - if needed)

2. **Copy to USB**:
   ```
   E:\EFI\BOOT\BOOTX64.EFI     (x64 UEFI bootloader)
   E:\EFI\BOOT\BOOTAA64.EFI    (ARM64 UEFI bootloader)
   E:\EFI\DriveRepair\DRIVEREPAIRX64.EFI
   E:\EFI\DriveRepair\DRIVEREPAIRAA64.EFI
   ```

3. **Boot from USB** - Done!

### Option 2: Use Rufus (More Complex)

Rufus is typically used for ISO files. To use Rufus, you'd need to:

1. **Create an ISO file** with the bootloaders
2. **Use Rufus to write the ISO** to USB

This is more complex and not necessary since the USB structure is already set up.

## What Files You Need

### Required Files for Full Application

1. **UEFI Bootloader (x64)**:
   - File: `drive-repair-uefi.efi`
   - Location: `E:\EFI\BOOT\BOOTX64.EFI`
   - Purpose: Boots the application on x64 UEFI systems

2. **UEFI Bootloader (ARM64)** (optional):
   - File: `drive-repair-uefi.efi` (ARM64 build)
   - Location: `E:\EFI\BOOT\BOOTAA64.EFI`
   - Purpose: Boots the application on ARM64 UEFI systems

3. **BIOS Bootloader** (optional, for legacy systems):
   - File: `drive-repair-bios` (raw binary)
   - Location: BIOS Boot Partition (requires special installation)

## Getting the Bootloaders

### Option A: Build on Linux (Recommended)

```bash
# On Linux system:
cd DriveRepair
rustup target add x86_64-unknown-uefi
cargo build --manifest-path src/boot/uefi/Cargo.toml --target x86_64-unknown-uefi --release

# Output will be at:
# src/boot/uefi/target/x86_64-unknown-uefi/release/drive-repair-uefi.efi
```

Then copy the `.efi` file to Windows and place on USB.

### Option B: Use Minimal UEFI Template

If building is still problematic, you can:
1. Download a minimal UEFI bootloader template
2. Integrate the DriveRepair code
3. Build the template (templates usually build easier)

### Option C: Wait for Windows Fix

The Rust target issue on Windows may be resolved in future Rust versions.

## Using Rufus (If You Create an ISO)

### Step 1: Create ISO with Bootloaders

You'd need to:
1. Create an ISO structure with EFI directory
2. Include the `.efi` files
3. Make it bootable

This requires tools like:
- `mkisofs` or `genisoimage` (Linux)
- `oscdimg` (Windows SDK)
- Or use a tool like `grub-mkrescue`

### Step 2: Use Rufus

1. Download Rufus: https://rufus.ie/
2. Select USB drive
3. Select "Disk or ISO image"
4. Choose your ISO file
5. Click "START"

**Note**: This will overwrite your current USB setup!

## Recommended Approach

**Since your USB structure is already perfect, I recommend:**

1. **Build bootloaders on Linux** (or get them from another source)
2. **Copy `.efi` files directly** to `E:\EFI\BOOT\`
3. **Test boot** - No Rufus needed!

The USB structure we created is already bootable - you just need the bootloader files.

## Quick Setup Script

Once you have the `.efi` files, use this:

```powershell
# Copy bootloaders to USB (assuming E: is your EFI partition)
Copy-Item "drive-repair-uefi.efi" "E:\EFI\BOOT\BOOTX64.EFI" -Force
Copy-Item "drive-repair-uefi.efi" "E:\EFI\DriveRepair\DRIVEREPAIRX64.EFI" -Force

# If you have ARM64 version:
# Copy-Item "drive-repair-uefi-arm64.efi" "E:\EFI\BOOT\BOOTAA64.EFI" -Force
```

## Summary

- ✅ USB structure: Ready
- ❌ Bootloaders: Need to be built (blocked on Windows)
- ✅ Solution: Build on Linux, copy `.efi` files to USB
- ❌ Rufus: Not needed (USB structure already set up)

**The USB is ready - you just need the bootloader files!**

