# USB Creation Guide
## DriveRepair by commstech v0.0.1

## Quick Start

### Option 1: Automated (Recommended)

**Run PowerShell as Administrator**, then:

```powershell
.\scripts\make_bootable_usb.ps1 -UsbDrive "E:"
```

This script will:
1. ✅ Try to build bootloaders (may fail due to compilation errors)
2. ✅ Setup USB structure (GPT, EFI partition)
3. ✅ Copy any available bootloaders
4. ✅ Provide next steps

### Option 2: Manual Setup

**Step 1: Setup USB Structure**

```powershell
# Run PowerShell as Administrator
.\scripts\setup_usb_only.ps1 -UsbDrive "E:"
```

**Step 2: Build Bootloaders (When Ready)**

```powershell
.\scripts\build_in_wsl.ps1
```

**Step 3: Copy Bootloaders**

```powershell
.\scripts\copy_bootloaders.ps1 -UsbDrive "E:" -UefiX64Path "src\boot\uefi\target\x86_64-unknown-uefi\release\drive-repair-uefi.efi"
```

## Current Status

### ✅ Ready
- USB structure setup script
- Bootloader copy script
- WSL build script
- Comprehensive USB maker script

### ⚠️ Pending
- Bootloader compilation (has errors, being fixed)
- Once bootloaders build successfully, USB will be fully functional

## USB Structure

After setup, your USB will have:

```
E:\
└── EFI\
    ├── BOOT\
    │   ├── BOOTX64.EFI    (UEFI x64 bootloader)
    │   └── BOOTAA64.EFI   (UEFI ARM64 bootloader, optional)
    └── DriveRepair\
        ├── DRIVEREPAIRX64.EFI
        └── DRIVEREPAIRAA64.EFI
```

## Testing

1. **Safely eject** the USB drive
2. **Insert** into target system
3. **Boot from USB** (UEFI mode)
4. **Test** the application

## Troubleshooting

### "Access to a CIM resource was not available"
- **Solution**: Run PowerShell as Administrator

### "Bootloaders not found"
- **Solution**: Bootloaders need to be built first
- Run: `.\scripts\build_in_wsl.ps1`
- Or wait for compilation errors to be fixed

### "WSL not found"
- **Solution**: Install WSL: `wsl --install`
- Or use `-SkipBuild` flag and provide pre-built bootloaders

## Next Steps

Once bootloaders are successfully built:
1. Run `.\scripts\make_bootable_usb.ps1 -UsbDrive "E:"`
2. Boot from USB
3. Test the application!

