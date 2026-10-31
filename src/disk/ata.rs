// ATA/IDE disk interface implementation
// Gate 0: fail-closed — unimplemented I/O returns Unsupported, never Ok(())

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// ATA disk implementation (experimental / unsupported on hosted OS)
pub struct AtaDisk {
    primary: bool,
    master: bool,
    sector_size: u64,
    total_sectors: u64,
    #[cfg(feature = "alloc")]
    model: String,
    #[cfg(feature = "alloc")]
    serial: String,
    #[cfg(feature = "alloc")]
    firmware: String,
}

impl AtaDisk {
    /// Create new ATA disk instance.
    /// May construct, but `is_ready` is false until real IDENTIFY succeeds.
    ///
    /// # Arguments
    /// * `primary` - true for primary channel (0x1F0), false for secondary (0x170)
    /// * `master` - true for master drive, false for slave
    pub fn new(primary: bool, master: bool) -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: ATA detection and IDENTIFY DEVICE not implemented.
        // Constructs a non-ready stub so callers can exist without fake successful I/O.
        Ok(Self {
            primary,
            master,
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

    /// Read ATA register
    #[allow(dead_code)]
    fn read_register(&self, _offset: u16) -> u8 {
        let _base = if self.primary { 0x1F0 } else { 0x170 };
        // EXPERIMENTAL/UNSUPPORTED: port I/O not implemented for ATA registers
        0
    }

    /// Write ATA register
    #[allow(dead_code)]
    fn write_register(&self, _offset: u16, _value: u8) {
        let _base = if self.primary { 0x1F0 } else { 0x170 };
        // EXPERIMENTAL/UNSUPPORTED: port I/O not implemented for ATA registers
    }

    /// Wait for drive to be ready
    #[allow(dead_code)]
    fn wait_ready(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: ready-wait polling not implemented
        Err(DiskError::Unsupported)
    }

    /// Send ATA command
    #[allow(dead_code)]
    fn send_command(&self, _command: u8, _lba: u64, _count: u8) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: ATA command submission not implemented
        Err(DiskError::Unsupported)
    }
}

impl Disk for AtaDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(DiskInfo {
            interface: DiskInterface::ATA,
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
        // EXPERIMENTAL/UNSUPPORTED: ATA READ SECTORS EXT not implemented
        Err(DiskError::Unsupported)
    }

    fn write_sectors(&self, _lba: u64, _count: u32, _buffer: &[u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: ATA WRITE SECTORS EXT not implemented
        Err(DiskError::Unsupported)
    }

    fn sector_size(&self) -> u64 {
        self.sector_size
    }

    fn total_sectors(&self) -> u64 {
        self.total_sectors
    }

    fn is_ready(&self) -> bool {
        // Fail-closed: not ready until IDENTIFY populates capacity
        self.total_sectors > 0
    }

    fn flush(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: FLUSH CACHE EXT not implemented
        Err(DiskError::Unsupported)
    }
}
