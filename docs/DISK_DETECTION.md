# Disk Detection Implementation Guide
## DriveRepair by commstech v0.0.1

## Overview
The disk detection module (`src/disk/detection.rs`) is responsible for enumerating and detecting all available drives in the system, regardless of interface type (ATA, SATA, NVMe, USB).

## Detection Methods

### UEFI Environment
- Use `uefi::proto::block::BlockIO` protocol
- Enumerate all block devices
- Get media information from protocol
- Filter for hard drives (exclude CD-ROM, floppy, etc.)

### BIOS Environment
- Use INT 13h, AH=0x48 (Get Drive Parameters)
- Probe ATA ports directly (0x1F0, 0x170)
- Detect drives on both primary and secondary channels
- Check for master/slave drives

### Windows/Linux (Development)
- Use platform-specific APIs
- Windows: `CreateFile` with `\\.\PhysicalDriveX`
- Linux: `/dev/sdX` or `/dev/nvmeXnY`
- Enumerate all block devices

## Detection Process

### 1. Initialize Detection
```rust
// Get detection context
// - UEFI: Get boot services
// - BIOS: Set up port I/O access
// - Windows/Linux: Open device handles
```

### 2. Enumerate Interfaces

#### ATA/SATA Detection
- Probe primary channel (0x1F0-0x1F7)
  - Check for master drive
  - Check for slave drive
- Probe secondary channel (0x170-0x177)
  - Check for master drive
  - Check for slave drive
- Send IDENTIFY DEVICE command (0xEC)
- Read identify data (512 bytes)
- Parse drive information

#### NVMe Detection
- Enumerate PCI devices
- Find NVMe controllers (Class 0x01, Subclass 0x08)
- Read controller registers
- Get namespace information
- Read identify namespace data

#### USB Detection
- Enumerate USB devices
- Find mass storage devices
- Get device information
- Read capacity information

### 3. Create Disk Objects
- For each detected drive:
  - Create appropriate disk object (AtaDisk, NvmeDisk, UsbDisk)
  - Populate disk information (size, model, serial, firmware)
  - Add to disk list

### 4. Return Disk List
- Return vector of disk objects
- Each disk implements `Disk` trait
- Can be used by repair engine

## Disk Information Structure

```rust
pub struct DiskInfo {
    pub interface: DiskInterface,  // ATA, SATA, NVMe, USB
    pub size_bytes: u64,           // Total size in bytes
    pub sector_size: u64,           // Sector size (512 or 4096)
    pub total_sectors: u64,        // Total sectors (64-bit)
    pub model: String,              // Drive model
    pub serial: String,             // Serial number
    pub firmware: String,          // Firmware version
}
```

## Implementation Details

### ATA Detection
1. **Select Drive**: Set Device/Head register (0x1F6)
   - Bit 4: 1 = LBA mode
   - Bit 6: 0 = master, 1 = slave
2. **Send IDENTIFY**: Command 0xEC to Command register (0x1F7)
3. **Wait for Ready**: Poll Status register (0x1F7)
   - BSY = 0, DRDY = 1
4. **Read Data**: Read 256 words from Data register (0x1F0)
5. **Parse Identify Data**:
   - Model: Words 27-46 (ASCII, byte-swapped)
   - Serial: Words 10-19 (ASCII, byte-swapped)
   - Firmware: Words 23-26 (ASCII, byte-swapped)
   - Capacity: Words 60-61 (28-bit LBA) or 100-103 (48-bit LBA)

### NVMe Detection
1. **PCI Enumeration**: Find NVMe controllers
2. **Read Controller Registers**:
   - CAP (Capabilities)
   - VS (Version)
   - CC (Controller Configuration)
3. **Identify Controller**: Send Admin Command
4. **Enumerate Namespaces**: Read namespace list
5. **Identify Namespace**: Get namespace information

### USB Detection
1. **Enumerate USB Devices**: Find mass storage class
2. **Get Device Descriptor**: Device information
3. **Get Configuration**: Interface information
4. **Read Capacity**: SCSI READ CAPACITY command
5. **Get Device Information**: Model, serial, etc.

## Error Handling

### Drive Not Ready
- Retry detection
- Check if drive is spinning up
- Timeout after reasonable delay

### Communication Error
- Retry command
- Check cable connections
- Report error to user

### Unsupported Drive
- Skip drive
- Log warning
- Continue enumeration

## Current Implementation Status

### Completed ✅
- Disk enumeration framework
- Disk information structure
- Interface type detection
- Size formatting utilities

### In Progress ⏳
- Actual ATA port I/O detection
- NVMe PCI enumeration
- USB mass storage detection
- UEFI Block I/O protocol integration

### Pending ⏳
- BIOS INT 13h detection
- Error recovery for detection
- Drive filtering (exclude CD-ROM, floppy)
- Performance optimization

## Notes

- Detection must work in bootable environment (no OS)
- Must support all interface types (ATA, SATA, NVMe, USB)
- Must handle drives from 64GB to 20TB
- Must use 64-bit LBA throughout
- Must be fast (user shouldn't wait long)

