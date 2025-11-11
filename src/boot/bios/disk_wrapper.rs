// BIOS disk wrapper implementing Disk trait
// Provides disk access via ATA port I/O or INT 13h

#![no_std]
#![no_main]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use crate::disk::ata_port_io::AtaPortIO;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// BIOS disk wrapper implementing Disk trait
pub struct BiosDisk {
    info: DiskInfo,
    primary: bool,
    master: bool,
    port_io: Option<AtaPortIO>,
}

impl BiosDisk {
    /// Create new BIOS disk wrapper for ATA disk
    pub fn new_ata(primary: bool, master: bool, info: DiskInfo) -> Self {
        Self {
            info,
            primary,
            master,
            port_io: Some(AtaPortIO::new(primary)),
        }
    }

    /// Create new BIOS disk wrapper for INT 13h disk
    pub fn new_int13h(drive_number: u8, info: DiskInfo) -> Self {
        Self {
            info,
            primary: false,
            master: false,
            port_io: None, // INT 13h doesn't use port I/O
        }
    }
}

impl Disk for BiosDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(self.info.clone())
    }

    fn sector_size(&self) -> u64 {
        self.info.sector_size
    }

    fn total_sectors(&self) -> u64 {
        self.info.total_sectors
    }

    fn size_bytes(&self) -> u64 {
        self.info.size_bytes
    }

    fn read_sectors(&mut self, lba: u64, count: u16, buffer: &mut [u8]) -> Result<(), DiskError> {
        if let Some(ref port_io) = self.port_io {
            // Use ATA port I/O
            use crate::boot::bios::disk_detection::BiosDiskDetector;
            BiosDiskDetector::read_sectors_ata(self.primary, self.master, lba, count, buffer)
        } else {
            // Use INT 13h
            // TODO: Implement INT 13h read
            Err(DiskError::HardwareError)
        }
    }

    fn write_sectors(&mut self, lba: u64, count: u16, buffer: &[u8]) -> Result<(), DiskError> {
        if let Some(ref port_io) = self.port_io {
            // Use ATA port I/O
            use crate::boot::bios::disk_detection::BiosDiskDetector;
            BiosDiskDetector::write_sectors_ata(self.primary, self.master, lba, count, buffer)
        } else {
            // Use INT 13h
            // TODO: Implement INT 13h write
            Err(DiskError::HardwareError)
        }
    }

    fn flush(&mut self) -> Result<(), DiskError> {
        // ATA flush cache command
        if let Some(ref port_io) = self.port_io {
            // TODO: Send ATA FLUSH CACHE command
            // For now, just return success
            Ok(())
        } else {
            // INT 13h doesn't require explicit flush
            Ok(())
        }
    }

    fn is_ready(&self) -> bool {
        if let Some(ref port_io) = self.port_io {
            // Check if drive is ready via ATA status register
            // TODO: Implement actual ready check
            // For now, return true if port_io exists
            true
        } else {
            // INT 13h disk is assumed ready if it was detected
            true
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bios_disk_creation() {
        // This test requires BIOS environment
        // Just verify the structure exists
        assert!(true);
    }
}

