# SMART Implementation Guide
## DriveRepair by commstech v0.0.1

## Overview
SMART (Self-Monitoring, Analysis, and Reporting Technology) provides drive health monitoring and predictive failure analysis.

## SMART Commands

### ATA SMART Commands
- **0xB0**: SMART command
  - **Subcommand 0xD0**: READ SMART DATA
  - **Subcommand 0xD1**: READ SMART THRESHOLDS
  - **Subcommand 0xD2**: ENABLE/DISABLE SMART
  - **Subcommand 0xD3**: EXECUTE OFFLINE IMMEDIATE
  - **Subcommand 0xD4**: EXECUTE OFF-LINE SHORT SELF-TEST
  - **Subcommand 0xD5**: EXECUTE OFF-LINE EXTENDED SELF-TEST

### Command Structure
```rust
// Send SMART command
fn smart_command(base: u16, subcommand: u8) -> Result<(), DiskError> {
    // Select drive
    outb(base + 6, 0xA0 | 0x40); // LBA mode, master
    
    // Set features register
    outb(base + 1, subcommand);
    
    // Set sector count
    outb(base + 2, 1);
    
    // Set LBA (not used for SMART)
    outb(base + 3, 0);
    outb(base + 4, 0);
    outb(base + 5, 0);
    
    // Send SMART command
    outb(base + 7, 0xB0);
    
    // Wait for ready
    wait_for_ready(base)?;
    
    Ok(())
}
```

## SMART Attributes

### Critical Attributes
1. **Reallocated Sectors Count** (ID: 0x05)
   - Indicates number of bad sectors remapped
   - High value = drive failure imminent

2. **Current Pending Sector Count** (ID: 0xC5)
   - Sectors waiting to be remapped
   - Non-zero = drive has issues

3. **Uncorrectable Sector Count** (ID: 0xC6)
   - Sectors that couldn't be recovered
   - Non-zero = data loss possible

4. **Power-On Hours** (ID: 0x09)
   - Total hours drive has been powered on
   - Used for wear estimation

5. **Power Cycle Count** (ID: 0x0C)
   - Number of power on/off cycles
   - High value = mechanical wear

### SSD-Specific Attributes
1. **Media Wearout Indicator** (ID: 0xE7)
   - SSD wear leveling status
   - 100 = new, 0 = worn out

2. **Host Writes** (ID: 0xF1)
   - Total data written to drive
   - Used for wear estimation

3. **Host Reads** (ID: 0xF2)
   - Total data read from drive
   - Used for wear estimation

## Attribute Structure

```rust
pub struct SmartAttribute {
    pub id: u8,              // Attribute ID
    pub flags: u16,          // Flags (critical, etc.)
    pub current: u8,         // Current value (0-255)
    pub worst: u8,           // Worst value (0-255)
    pub threshold: u8,       // Threshold value
    pub raw_value: u64,      // Raw value (vendor-specific)
}

pub struct SmartData {
    pub version: u16,        // SMART version
    pub attributes: [SmartAttribute; 30], // 30 attributes
    pub offline_data_collection_status: u8,
    pub self_test_execution_status: u8,
    pub total_time: u16,     // Total time for offline data collection
    pub error_log_pointer: u8,
}
```

## Implementation

### Read SMART Data
```rust
fn read_smart_data(base: u16) -> Result<SmartData, DiskError> {
    // Send SMART READ DATA command
    smart_command(base, 0xD0)?;
    
    // Wait for data ready
    wait_for_drq(base)?;
    
    // Read 512 bytes of SMART data
    let mut buffer = [0u8; 512];
    for i in 0..256 {
        let word = inw(base);
        buffer[i * 2] = word as u8;
        buffer[i * 2 + 1] = (word >> 8) as u8;
    }
    
    // Parse SMART data
    parse_smart_data(&buffer)
}
```

### Parse SMART Data
```rust
fn parse_smart_data(buffer: &[u8]) -> Result<SmartData, DiskError> {
    let mut data = SmartData::default();
    
    // Parse version (offset 0x00-0x01)
    data.version = u16::from_le_bytes([buffer[0], buffer[1]]);
    
    // Parse attributes (offset 0x02-0x1D1, 12 bytes each)
    for i in 0..30 {
        let offset = 2 + (i * 12);
        data.attributes[i] = SmartAttribute {
            id: buffer[offset],
            flags: u16::from_le_bytes([buffer[offset + 1], buffer[offset + 2]]),
            current: buffer[offset + 3],
            worst: buffer[offset + 4],
            threshold: buffer[offset + 5],
            raw_value: u64::from_le_bytes([
                buffer[offset + 6],
                buffer[offset + 7],
                buffer[offset + 8],
                buffer[offset + 9],
                buffer[offset + 10],
                buffer[offset + 11],
                0,
                0,
            ]),
        };
    }
    
    // Parse status fields
    data.offline_data_collection_status = buffer[0x1D2];
    data.self_test_execution_status = buffer[0x1D3];
    data.total_time = u16::from_le_bytes([buffer[0x1D4], buffer[0x1D5]]);
    data.error_log_pointer = buffer[0x1D6];
    
    Ok(data)
}
```

### Health Status Calculation
```rust
fn calculate_health_status(data: &SmartData) -> SmartHealthStatus {
    // Check critical attributes
    let reallocated = data.attributes[0x05].current;
    let pending = data.attributes[0xC5].current;
    let uncorrectable = data.attributes[0xC6].current;
    
    // Determine health status
    if uncorrectable > 0 {
        SmartHealthStatus::Critical
    } else if pending > 0 || reallocated > data.attributes[0x05].threshold {
        SmartHealthStatus::Warning
    } else {
        SmartHealthStatus::Good
    }
}
```

## NVMe SMART

### NVMe SMART Log
- **Log ID**: 0x02 (SMART/Health Information)
- **Command**: GET LOG PAGE
- **Namespace**: 0xFFFFFFFF (global)

### Structure
```rust
pub struct NvmeSmartLog {
    pub critical_warning: u8,
    pub temperature: u16,
    pub available_spare: u8,
    pub available_spare_threshold: u8,
    pub percentage_used: u8,
    pub data_units_read: u128,
    pub data_units_written: u128,
    pub host_reads: u128,
    pub host_writes: u128,
    pub controller_busy_time: u128,
    pub power_cycles: u32,
    pub power_on_hours: u32,
    pub unsafe_shutdowns: u32,
    pub media_errors: u32,
    pub num_error_log_entries: u32,
}
```

## Implementation Status

### Completed ✅
- SMART interface framework
- Attribute structure definition
- Basic attribute parsing

### In Progress ⏳
- ATA SMART command implementation
- NVMe SMART log reading
- Health status calculation
- Wear leveling awareness

### Pending ⏳
- Self-test execution
- Error log reading
- Predictive failure analysis
- Integration with repair engine

## Notes

- SMART provides early warning of drive failure
- Critical attributes should be monitored continuously
- SSD wear leveling requires special attention
- NVMe SMART is different from ATA SMART (different structure)

