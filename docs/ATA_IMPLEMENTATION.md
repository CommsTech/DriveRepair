# ATA Port I/O Implementation Guide
## DriveRepair by commstech v0.0.1

## ATA Port Addresses

### Primary Channel
- **0x1F0**: Data Register (read/write)
- **0x1F1**: Error Register (read) / Features Register (write)
- **0x1F2**: Sector Count Register
- **0x1F3**: LBA Low (bits 0-7)
- **0x1F4**: LBA Mid (bits 8-15)
- **0x1F5**: LBA High (bits 16-23)
- **0x1F6**: Device/Head Register (bits 24-27 in LBA mode)
- **0x1F7**: Status Register (read) / Command Register (write)

### Secondary Channel
- **0x170**: Data Register (read/write)
- **0x171**: Error Register (read) / Features Register (write)
- **0x172**: Sector Count Register
- **0x173**: LBA Low (bits 0-7)
- **0x174**: LBA Mid (bits 8-15)
- **0x175**: LBA High (bits 16-23)
- **0x176**: Device/Head Register (bits 24-27 in LBA mode)
- **0x177**: Status Register (read) / Command Register (write)

## ATA Commands

### 28-bit LBA Commands
- **0x20**: READ SECTORS
- **0x30**: WRITE SECTORS
- **0xEC**: IDENTIFY DEVICE

### 48-bit LBA Commands (Extended)
- **0x24**: READ SECTORS EXT
- **0x34**: WRITE SECTORS EXT
- **0xEA**: FLUSH CACHE EXT
- **0xEC**: IDENTIFY DEVICE (same as 28-bit)

## Status Register Bits
- **Bit 7 (BSY)**: Busy
- **Bit 6 (DRDY)**: Drive Ready
- **Bit 5 (DF)**: Drive Fault
- **Bit 4 (DSC)**: Drive Seek Complete
- **Bit 3 (DRQ)**: Data Request
- **Bit 2 (CORR)**: Corrected Data
- **Bit 1 (IDX)**: Index
- **Bit 0 (ERR)**: Error

## Error Register Bits (when ERR=1)
- **Bit 7**: Bad Block
- **Bit 6**: Uncorrectable Data Error
- **Bit 5**: Media Change Request
- **Bit 4**: ID Not Found
- **Bit 3**: Media Change
- **Bit 2**: Aborted Command
- **Bit 1**: Track 0 Not Found
- **Bit 0**: Address Mark Not Found

## Implementation Steps

### 1. Port I/O Functions
```rust
// Read from port
unsafe fn inb(port: u16) -> u8;

// Write to port
unsafe fn outb(port: u16, value: u8);

// Wait for drive ready
fn wait_for_ready(base: u16, timeout_ms: u32) -> Result<(), DiskError>;

// Wait for data request
fn wait_for_drq(base: u16, timeout_ms: u32) -> Result<(), DiskError>;
```

### 2. ATA Command Functions
```rust
// Send ATA command
fn send_ata_command(
    base: u16,
    command: u8,
    lba: u64,
    sector_count: u8,
) -> Result<(), DiskError>;

// Read sectors using 28-bit LBA
fn read_sectors_28bit(
    base: u16,
    lba: u32,
    count: u8,
    buffer: &mut [u8],
) -> Result<(), DiskError>;

// Read sectors using 48-bit LBA
fn read_sectors_48bit(
    base: u16,
    lba: u64,
    count: u16,
    buffer: &mut [u8],
) -> Result<(), DiskError>;
```

### 3. Error Handling
- Check status register for errors
- Retry on transient errors
- Handle timeout conditions
- Report specific error types

## Notes from SPINRITE.EXE Analysis

### Found Patterns
- INT 13h calls at: 0x142FA, 0x18478, 0x259DE
- Port I/O (0x1F0) at: 0x23E, 0x1CBFC
- Port I/O (0x170) at: 0x103A1, 0x21F19

### Expected Implementation
- Uses both INT 13h and direct port I/O
- Likely supports 28-bit LBA (32-bit limitation)
- May have 48-bit LBA support (to be confirmed)
- Error recovery with retries

## Platform-Specific Notes

### UEFI Environment
- Use UEFI Block I/O Protocol
- No direct port I/O access
- Use `uefi::proto::block::BlockIO`

### BIOS Environment
- Direct port I/O access available
- Use `x86_64::instructions::port::Port`
- Or inline assembly

### Windows/Linux (Development)
- Use platform-specific APIs
- Windows: `CreateFile`, `DeviceIoControl`
- Linux: `/dev/sdX` file access

