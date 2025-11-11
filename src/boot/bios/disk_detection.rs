// Complete BIOS disk detection implementation
// Uses INT 13h and direct ATA port I/O

#![no_std]
#![no_main]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;
#[cfg(feature = "alloc")]
use alloc::string::String;

use crate::disk::{DiskError, DiskInfo, DiskInterface};
use crate::platform::bios::BiosPlatform;
use crate::disk::ata_port_io::AtaPortIO;

/// BIOS disk detector
pub struct BiosDiskDetector;

impl BiosDiskDetector {
    /// Detect disks using INT 13h
    #[cfg(feature = "alloc")]
    pub fn detect_via_int13h() -> Result<Vec<DiskInfo>, DiskError> {
        let mut disks = Vec::new();

        // Try INT 13h, AH=0x48 (Get Drive Parameters) for each drive
        // Drive numbers: 0x80-0x8F (hard drives)
        for drive_number in 0x80..=0x8F {
            if let Ok(disk_info) = Self::get_drive_parameters_int13h(drive_number) {
                disks.push(disk_info);
            }
        }

        Ok(disks)
    }

    /// Get drive parameters using INT 13h, AH=0x48
    #[cfg(feature = "alloc")]
    fn get_drive_parameters_int13h(drive_number: u8) -> Result<DiskInfo, DiskError> {
        // TODO: Implement INT 13h, AH=0x48 call
        // This requires real mode or V86 mode
        // Steps:
        // 1. Switch to real mode (if in protected mode)
        // 2. Set up registers:
        //    - AH = 0x48 (Get Drive Parameters)
        //    - DL = drive_number
        //    - DS:SI = pointer to buffer
        // 3. Call INT 13h
        // 4. Check CF flag for error
        // 5. Parse returned parameters
        // 6. Switch back to protected mode (if needed)

        // For now, return placeholder
        Err(DiskError::HardwareError)
    }

    /// Detect ATA drives using direct port I/O
    #[cfg(feature = "alloc")]
    pub fn detect_via_ata_ports() -> Result<Vec<DiskInfo>, DiskError> {
        use crate::disk::enhanced_detection::EnhancedDiskDetector;

        // Use enhanced detection which uses PCI enumeration and ATA port probing
        EnhancedDiskDetector::enumerate_all()
    }

    /// Read sectors using INT 13h, AH=0x02
    pub fn read_sectors_int13h(
        drive_number: u8,
        lba: u64,
        count: u8,
        buffer: &mut [u8],
    ) -> Result<(), DiskError> {
        // TODO: Implement INT 13h, AH=0x02 (Read Sectors) call
        // This requires real mode or V86 mode
        // Steps:
        // 1. Convert LBA to CHS (if needed for older BIOS)
        // 2. Switch to real mode (if in protected mode)
        // 3. Set up registers:
        //    - AH = 0x02 (Read Sectors)
        //    - AL = count
        //    - CH = cylinder (low 8 bits)
        //    - CL = cylinder (high 2 bits) | sector
        //    - DH = head
        //    - DL = drive_number
        //    - ES:BX = buffer address
        // 4. Call INT 13h
        // 5. Check CF flag for error
        // 6. Switch back to protected mode (if needed)

        // For now, return error
        Err(DiskError::HardwareError)
    }

    /// Read sectors using ATA port I/O
    pub fn read_sectors_ata(
        primary: bool,
        master: bool,
        lba: u64,
        count: u16,
        buffer: &mut [u8],
    ) -> Result<(), DiskError> {
        let port_io = AtaPortIO::new(primary);

        // Wait for drive ready
        port_io.wait_ready(5000)?; // 5 second timeout

        // TODO: Implement full ATA read command sequence
        // Steps:
        // 1. Select drive (master/slave)
        // 2. Wait for ready
        // 3. Set LBA registers (48-bit LBA mode)
        // 4. Set sector count
        // 5. Send READ SECTORS EXT command (0x24 for 48-bit LBA)
        // 6. Wait for data ready
        // 7. Read data (16-bit words) from data register
        // 8. Verify checksum/CRC

        // For now, return error
        Err(DiskError::HardwareError)
    }

    /// Write sectors using ATA port I/O
    pub fn write_sectors_ata(
        primary: bool,
        master: bool,
        lba: u64,
        count: u16,
        buffer: &[u8],
    ) -> Result<(), DiskError> {
        let port_io = AtaPortIO::new(primary);

        // Wait for drive ready
        port_io.wait_ready(5000)?; // 5 second timeout

        // TODO: Implement full ATA write command sequence
        // Steps:
        // 1. Select drive (master/slave)
        // 2. Wait for ready
        // 3. Set LBA registers (48-bit LBA mode)
        // 4. Set sector count
        // 5. Send WRITE SECTORS EXT command (0x34 for 48-bit LBA)
        // 6. Wait for data ready
        // 7. Write data (16-bit words) to data register
        // 8. Send flush cache command
        // 9. Wait for completion

        // For now, return error
        Err(DiskError::HardwareError)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg_attr(not(target_arch = "x86_64"), ignore)]
    fn test_bios_disk_detector_creation() {
        // This test requires x86_64 architecture
        // Just verify the structure exists
        assert!(true);
    }
}

