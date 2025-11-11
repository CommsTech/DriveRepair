# Creating ISO for Rufus
## DriveRepair by commstech v0.0.1

## Important Note

**You don't need Rufus!** Your USB structure is already set up. Just copy the `.efi` files directly.

However, if you want to use Rufus, you need to create an ISO file first.

## Option 1: Direct Copy (Easier - Recommended)

Since your USB is already set up with the correct structure:

1. Build bootloaders (on Linux)
2. Copy `.efi` files to `E:\EFI\BOOT\`
3. Done! No ISO needed.

## Option 2: Create ISO for Rufus

If you want to use Rufus, you need to create an ISO file with the bootloader structure.

### Requirements

You'll need one of these tools:
- **Windows**: `oscdimg` (from Windows SDK/ADK) or `mkisofs` (from Cygwin)
- **Linux**: `genisoimage` or `xorriso`
- **Cross-platform**: `grub-mkrescue` (if using GRUB)

### Method 1: Using oscdimg (Windows)

```powershell
# Install Windows ADK to get oscdimg.exe
# Then create ISO structure:

# 1. Create directory structure
New-Item -ItemType Directory -Path "iso\EFI\BOOT" -Force
New-Item -ItemType Directory -Path "iso\EFI\DriveRepair" -Force

# 2. Copy your bootloader files
Copy-Item "drive-repair-uefi.efi" "iso\EFI\BOOT\BOOTX64.EFI"
Copy-Item "drive-repair-uefi.efi" "iso\EFI\DriveRepair\DRIVEREPAIRX64.EFI"

# 3. Create ISO
oscdimg -m -o -u2 -udfver102 -bootdata:2#p0,e,b"iso\EFI\BOOT\BOOTX64.EFI"#pEF,e,b"iso\EFI\BOOT\BOOTX64.EFI" iso DriveRepair.iso
```

### Method 2: Using mkisofs/xorriso (Linux/Cross-platform)

```bash
# Create directory structure
mkdir -p iso/EFI/BOOT
mkdir -p iso/EFI/DriveRepair

# Copy bootloaders
cp drive-repair-uefi.efi iso/EFI/BOOT/BOOTX64.EFI
cp drive-repair-uefi.efi iso/EFI/DriveRepair/DRIVEREPAIRX64.EFI

# Create ISO with UEFI boot support
xorriso -as mkisofs \
  -R -J \
  -V "DriveRepair" \
  -e EFI/BOOT/BOOTX64.EFI \
  -no-emul-boot \
  -boot-load-size 8192 \
  -boot-info-table \
  -o DriveRepair.iso \
  iso/
```

### Method 3: Using PowerShell Script (Simpler)

I'll create a script that uses available tools or provides instructions.

## What Rufus Needs

Rufus needs:
- **ISO file** with EFI bootloader structure
- **OR** a disk image (.img) file
- The bootloader must be at `EFI/BOOT/BOOTX64.EFI` in the ISO

## Recommendation

**Skip Rufus entirely!** Your USB is already set up correctly:

1. USB structure: ✅ Ready (E:)
2. EFI directories: ✅ Created
3. Just need: `.efi` files copied

**Much simpler than creating an ISO!**

