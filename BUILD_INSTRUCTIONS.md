# Build Instructions
## DriveRepair by commstech v0.0.1

## Prerequisites

1. **Install Rust** (if not already installed):
   ```powershell
   # Download and run rustup-init.exe from https://rustup.rs/
   ```

2. **Install Required Rust Targets**:
   ```powershell
   rustup target add x86_64-unknown-uefi
   rustup target add aarch64-unknown-uefi
   rustup target add x86_64-unknown-none
   ```

## Building Bootloaders

### Option 1: Use the Build Script (Recommended)

```powershell
.\scripts\build_bootloaders.ps1
```

This script will:
- Check if required targets are installed
- Install missing targets automatically
- Build all bootloaders (UEFI x64, UEFI ARM64, BIOS)
- Report build results

### Option 2: Manual Build

#### Build UEFI x64 Bootloader:
```powershell
cargo build --manifest-path src\boot\uefi\Cargo.toml --target x86_64-unknown-uefi --release
```

Output: `src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi`

#### Build UEFI ARM64 Bootloader:
```powershell
cargo build --manifest-path src\boot\uefi\Cargo.toml --target aarch64-unknown-uefi --release
```

Output: `src\boot\uefi\target\aarch64-unknown-uefi\release\drive-repair-uefi.efi`

#### Build BIOS Bootloader:
```powershell
cargo build --manifest-path src\boot\bios\Cargo.toml --target x86_64-unknown-none --release
```

Output: `src\boot\bios\target\x86_64-unknown-none\release\drive-repair-bios`

## Creating Bootable USB

After building the bootloaders, create the bootable USB drive:

```powershell
.\scripts\create_usb.ps1 -UsbDrive "F:"
```

**Note:** Run PowerShell as Administrator for USB creation.

The script will:
1. Convert disk to GPT (if needed)
2. Create EFI System Partition (FAT32)
3. Create BIOS Boot Partition
4. Copy bootloaders to appropriate locations
5. Set up boot configuration

## Bootloader Locations on USB

After USB creation, bootloaders will be located at:

- **UEFI x64**: `F:\EFI\BOOT\BOOTX64.EFI` and `F:\EFI\DriveRepair\DRIVEREPAIRX64.EFI`
- **UEFI ARM64**: `F:\EFI\BOOT\BOOTAA64.EFI` and `F:\EFI\DriveRepair\DRIVEREPAIRAA64.EFI`
- **BIOS**: Installed to BIOS Boot Partition (hidden)

## Testing

1. **UEFI Boot**: 
   - Set BIOS/UEFI to boot from USB
   - Select UEFI boot option
   - Bootloader should start automatically

2. **BIOS Boot**:
   - Set BIOS to legacy/CSM mode
   - Boot from USB
   - Bootloader should start automatically

## Troubleshooting

### Build Errors

- **Missing targets**: Run `rustup target add <target-name>`
- **Missing dependencies**: Run `cargo build` in the root directory first
- **UEFI build errors**: Ensure `uefi` and `uefi-services` crates are available

### USB Creation Errors

- **Access denied**: Run PowerShell as Administrator
- **Disk not found**: Check drive letter with `Get-Disk`
- **Partition errors**: Ensure disk is not in use (close all file explorers)

### Boot Errors

- **Bootloader not found**: Verify bootloaders were copied correctly
- **UEFI not booting**: Check if system supports UEFI boot
- **BIOS not booting**: Check if system supports legacy boot

## Next Steps

After successful build and USB creation:

1. Test boot on target system
2. Verify disk detection works
3. Test repair functionality
4. Report any issues or improvements needed

