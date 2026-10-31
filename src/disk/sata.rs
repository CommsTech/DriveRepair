// SATA disk interface via AHCI controller
// Gate 0: fail-closed — detect and I/O return Unsupported

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// AHCI controller structure
pub struct AhciController {
    base_address: u64,
    port_count: u32,
}

/// SATA disk implementation via AHCI
pub struct SataDisk {
    controller: AhciController,
    port: u32,
    sector_size: u64,
    total_sectors: u64,
    #[cfg(feature = "alloc")]
    model: String,
    #[cfg(feature = "alloc")]
    serial: String,
    #[cfg(feature = "alloc")]
    firmware: String,
}

impl AhciController {
    /// Detect and initialize AHCI controller
    pub fn detect() -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: AHCI PCI enumeration and init not implemented
        Err(DiskError::Unsupported)
    }

    /// Get number of ports
    pub fn port_count(&self) -> u32 {
        self.port_count
    }
}

impl SataDisk {
    /// Create new SATA disk instance
    ///
    /// # Arguments
    /// * `controller` - AHCI controller instance
    /// * `port` - Port number (0-based)
    pub fn new(controller: AhciController, port: u32) -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SATA port identify not implemented
        Ok(Self {
            controller,
            port,
            sector_size: SECTOR_SIZE_512,
            total_sectors: 0,
            #[cfg(feature = "alloc")]
            model: String::new(),
            #[cfg(feature = "alloc")]
            serial: String::new(),
            #[cfg(feature = "alloc")]
            firmware: String::new(),
        })
    }

    /// Send ATA command via AHCI
    #[allow(dead_code)]
    fn send_command(&self, _command: u8, _lba: u64, _count: u16) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: AHCI command submission not implemented
        Err(DiskError::Unsupported)
    }

    #[allow(dead_code)]
    fn wait_ready(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: AHCI port ready wait not implemented
        Err(DiskError::Unsupported)
    }
}

impl Disk for SataDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(DiskInfo {
            interface: DiskInterface::SATA,
            size_bytes: self.size_bytes(),
            sector_size: self.sector_size,
            total_sectors: self.total_sectors,
            #[cfg(feature = "alloc")]
            model: self.model.clone(),
            #[cfg(not(feature = "alloc"))]
            model: "",
            #[cfg(feature = "alloc")]
            serial: self.serial.clone(),
            #[cfg(not(feature = "alloc"))]
            serial: "",
            #[cfg(feature = "alloc")]
            firmware: self.firmware.clone(),
            #[cfg(not(feature = "alloc"))]
            firmware: "",
        })
    }

    fn read_sectors(&self, _lba: u64, _count: u32, _buffer: &mut [u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: AHCI read not implemented
        Err(DiskError::Unsupported)
    }

    fn write_sectors(&self, _lba: u64, _count: u32, _buffer: &[u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: AHCI write not implemented
        Err(DiskError::Unsupported)
    }

    fn sector_size(&self) -> u64 {
        self.sector_size
    }

    fn total_sectors(&self) -> u64 {
        self.total_sectors
    }

    fn is_ready(&self) -> bool {
        self.total_sectors > 0
    }

    fn flush(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: FLUSH CACHE EXT via AHCI not implemented
        Err(DiskError::Unsupported)
    }
}
