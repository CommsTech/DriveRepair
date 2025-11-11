# Bootloader Implementation Guide
## DriveRepair by commstech v0.0.1

## UEFI Bootloader

### Overview
The UEFI bootloader runs in a UEFI environment and uses UEFI protocols to access disks and provide the repair interface.

### Key Components

#### 1. Entry Point
- Located in `src/boot/uefi/main.rs`
- Uses `#[entry]` attribute for UEFI entry point
- Initializes UEFI services

#### 2. Disk Access
- Use `uefi::proto::block::BlockIO` protocol
- Enumerate all block devices
- Access sectors using 64-bit LBA
- No direct port I/O (UEFI handles hardware abstraction)

#### 3. Implementation Steps

```rust
// 1. Initialize UEFI services
uefi_services::init(&mut st)?;

// 2. Get boot services
let boot_services = st.boot_services();

// 3. Locate Block I/O protocol
let handles = boot_services.find_handles::<BlockIO>()?;

// 4. Open each block device
for handle in handles {
    let block_io = boot_services.open_protocol_exclusive::<BlockIO>(handle)?;
    
    // 5. Get media information
    let media = block_io.media();
    
    // 6. Read/write sectors using BlockIO
    block_io.read_blocks(media, lba, buffer)?;
}
```

### Features
- ✅ UEFI environment support
- ✅ 64-bit LBA addressing
- ✅ GPT partition table support
- ✅ Multiple disk support
- ⏳ User interface (text mode)
- ⏳ Disk selection menu
- ⏳ Repair engine integration

## BIOS Bootloader

### Overview
The BIOS bootloader runs in a legacy BIOS environment and uses INT 13h BIOS calls and direct hardware access.

### Key Components

#### 1. Entry Point
- Located in `src/boot/bios/main.rs`
- Uses `#[no_mangle]` and `extern "C"` for BIOS entry
- Starts in real mode (16-bit)

#### 2. Boot Process
1. **Real Mode Setup** (16-bit)
   - Set up stack
   - Initialize segment registers
   - Set up interrupt vectors

2. **Transition to Protected Mode** (32-bit)
   - Set up GDT (Global Descriptor Table)
   - Enable protected mode
   - Set up 32-bit stack

3. **Long Mode Setup** (64-bit, optional)
   - Set up paging
   - Enable long mode
   - Set up 64-bit stack

#### 3. Disk Access Methods

**INT 13h BIOS Calls**:
```rust
// Read sectors using INT 13h Extended Read
// AH = 0x42 (Extended Read)
// DS:SI = Address packet
// DL = Drive number (0x80 = first hard drive)

struct DiskAddressPacket {
    size: u8,        // Size of packet (16 or 24)
    reserved: u8,
    sectors: u16,    // Number of sectors to read
    offset: u16,     // Buffer offset
    segment: u16,    // Buffer segment
    lba_low: u32,    // LBA low 32 bits
    lba_high: u32,   // LBA high 32 bits
}
```

**Direct Port I/O** (for ATA drives):
- Use port addresses 0x1F0-0x1F7 (primary) or 0x170-0x177 (secondary)
- Send ATA commands directly
- Read/write data registers

### Implementation Steps

1. **Initialize VGA Text Mode**
   - Clear screen
   - Set up text mode (80x25)
   - Print welcome message

2. **Detect Disks**
   - Use INT 13h, AH=0x48 (Get Drive Parameters)
   - Or probe ATA ports directly
   - Enumerate all available drives

3. **Show Disk List**
   - Display detected drives
   - Show drive information (size, model, etc.)

4. **User Selection**
   - Prompt user to select drive
   - Validate selection

5. **Run Repair**
   - Initialize repair engine
   - Run surface scan
   - Display progress
   - Handle errors

### Features
- ⏳ Real mode initialization
- ⏳ Protected mode transition
- ⏳ VGA text mode support
- ⏳ INT 13h disk access
- ⏳ Direct ATA port I/O
- ⏳ User interface
- ⏳ Repair engine integration

## Bootable USB Creation

### GPT Partition Table
- **EFI System Partition (ESP)**: FAT32, ~100MB
  - Contains UEFI bootloader
  - Mount point: `/boot/efi` or `\EFI\BOOT\`
  
- **BIOS Boot Partition**: ~1MB
  - Contains BIOS bootloader
  - Used by GRUB or similar bootloader

### File Structure
```
USB Drive (F:)
├── EFI/
│   └── BOOT/
│       ├── BOOTX64.EFI (UEFI x86_64 bootloader)
│       └── BOOTAA64.EFI (UEFI ARM64 bootloader)
├── boot/
│   └── bios/
│       └── boot.bin (BIOS bootloader)
└── drive-repair/
    └── drive-repair.efi (Main application)
```

### Boot Process

#### UEFI Boot
1. UEFI firmware scans ESP
2. Finds `\EFI\BOOT\BOOTX64.EFI` or `BOOTAA64.EFI`
3. Loads and executes bootloader
4. Bootloader initializes UEFI services
5. Bootloader loads main application

#### BIOS Boot
1. BIOS reads MBR (Master Boot Record)
2. MBR loads bootloader from BIOS Boot Partition
3. Bootloader initializes real mode
4. Bootloader transitions to protected mode
5. Bootloader loads main application

## Implementation Priorities

### High Priority
1. ✅ UEFI entry point skeleton
2. ✅ BIOS entry point skeleton
3. ⏳ UEFI disk enumeration
4. ⏳ BIOS disk detection
5. ⏳ User interface (text mode)

### Medium Priority
1. ⏳ Disk selection menu
2. ⏳ Repair engine integration
3. ⏳ Progress display
4. ⏳ Error handling

### Low Priority
1. ⏳ Advanced UI features
2. ⏳ Configuration options
3. ⏳ Logging and diagnostics

## Notes

- UEFI bootloader is simpler (uses UEFI protocols)
- BIOS bootloader is more complex (needs mode transitions)
- Both need to support 64-bit LBA for large drives
- Both need user interface for drive selection
- Both need integration with repair engine

