# Drive Repair Tool

Modern drive repair utility built in Rust, supporting drives from 64GB to 20TB with UEFI/BIOS bootable USB support.

## Features

- **64-bit LBA Addressing**: Supports drives up to 20TB (fixes 1TB limitation of original SpinRite)
- **Multiple Interface Support**: ATA, SATA, NVMe, and USB drives
- **SMART Monitoring**: Health status, predictive failure analysis, wear leveling awareness
- **Advanced Repair**: Low-level sector reading, error correction, surface scanning, TRIM support
- **Bootable USB**: Hybrid UEFI/BIOS bootable USB drive creation
- **Mac Compatibility**: Support for Mac hardware

## Project Structure

```
DriveRepair/
├── src/
│   ├── disk/          # Disk interface modules (ATA, SATA, NVMe, USB)
│   ├── repair/        # Repair engine algorithms
│   ├── smart/         # SMART interface implementation
│   ├── ui/            # User interface components
│   ├── boot/          # Bootloader code (UEFI and BIOS)
│   └── lib.rs         # Main library module
├── docs/
│   ├── REVERSE_ENGINEERING.md  # Reverse engineering notes
│   └── ARCHITECTURE.md         # System architecture documentation
├── scripts/
│   └── create_usb.ps1          # USB creation script
└── Cargo.toml                  # Rust project configuration
```

## Building

### Prerequisites

- Rust 1.90.0 or later
- UEFI target: `rustup target add x86_64-unknown-uefi`
- BIOS target: `rustup target add x86_64-unknown-none`

### Build Commands

```powershell
# Build for standard library (development/testing)
cargo build --release

# Build for UEFI
cargo build --target x86_64-unknown-uefi --release

# Build for BIOS
cargo build --target x86_64-unknown-none --release
```

## Creating Bootable USB

Use the provided PowerShell script to create a bootable USB drive:

```powershell
# Run as Administrator
.\scripts\create_usb.ps1 -UsbDrive "E:"
```

The script will:
1. Clean and initialize the USB drive with GPT partition table
2. Create EFI System Partition (ESP) for UEFI boot
3. Create BIOS Boot Partition for legacy boot
4. Create data partition for logs/reports
5. Copy bootloaders to appropriate locations
6. Set up boot configuration

## USB Drive Layout

```
USB Drive Layout:
├── Protective MBR (for BIOS compatibility)
├── GPT Partition Table
├── EFI System Partition (FAT32, ~100MB)
│   ├── EFI/
│   │   ├── BOOT/
│   │   │   └── BOOTX64.EFI (UEFI bootloader)
│   │   └── DriveRepair/
│   │       └── DRIVEREPAIR.EFI (main application)
├── Data Partition (optional, for logs/reports)
└── BIOS Boot Partition (for legacy boot)
```

## Usage

### Bootable Environment

1. Boot from the USB drive (UEFI or BIOS)
2. Select drive to repair from the list
3. Configure repair options (scan pattern, retry count, etc.)
4. Start repair process
5. Monitor progress and view statistics

### Development Version

```powershell
cargo run
```

## Technical Details

### Addressing 1TB Limitation

The original SpinRite uses 32-bit LBA (Logical Block Addressing), limiting it to:
- 2^32 sectors × 512 bytes = 2TB theoretical maximum
- Practical limitations may restrict to 1TB

The new implementation uses:
- 64-bit LBA throughout
- Supports drives up to 2^64 sectors (effectively unlimited)
- Proper handling of 4KB sector sizes

### Modern Drive Support

- **NVMe**: Direct PCIe controller access, namespace support
- **SATA**: AHCI protocol implementation, NCQ support
- **USB**: Mass storage protocol, multiple LUN support
- **SSDs**: TRIM, wear leveling awareness, secure erase

## Reverse Engineering

See `docs/REVERSE_ENGINEERING.md` for notes on reverse engineering SPINRITE.EXE.

## Architecture

See `docs/ARCHITECTURE.md` for detailed system architecture documentation.

## License

[To be determined]

## Contributing

[To be determined]

