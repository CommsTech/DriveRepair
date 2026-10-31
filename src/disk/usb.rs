// USB mass storage device interface
// Gate 0: fail-closed — unimplemented I/O returns Unsupported

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// USB disk implementation
pub struct UsbDisk {
    device_address: u8,
    sector_size: u64,
    total_sectors: u64,
    #[cfg(feature = "alloc")]
    model: String,
    #[cfg(feature = "alloc")]
    serial: String,
    #[cfg(feature = "alloc")]
    firmware: String,
}

impl UsbDisk {
    /// Create new USB disk instance
    ///
    /// # Arguments
    /// * `device_address` - USB device address
    pub fn new(device_address: u8) -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: USB mass-storage enumeration not implemented
        Ok(Self {
            device_address,
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

    /// Send SCSI command via USB
    #[allow(dead_code)]
    fn send_scsi_command(&self, _command: &[u8], _data: &mut [u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: USB BOT / SCSI command path not implemented
        Err(DiskError::Unsupported)
    }

    #[allow(dead_code)]
    fn send_command(&self, _command: &[u8], _data: &mut [u8]) -> Result<(), DiskError> {
        self.send_scsi_command(_command, _data)
    }

    #[allow(dead_code)]
    fn wait_ready(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: USB device ready wait not implemented
        Err(DiskError::Unsupported)
    }
}

impl Disk for UsbDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(DiskInfo {
            interface: DiskInterface::USB,
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
        // EXPERIMENTAL/UNSUPPORTED: USB SCSI READ not implemented
        Err(DiskError::Unsupported)
    }

    fn write_sectors(&self, _lba: u64, _count: u32, _buffer: &[u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: USB SCSI WRITE not implemented
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
        // EXPERIMENTAL/UNSUPPORTED: SCSI SYNCHRONIZE CACHE not implemented
        Err(DiskError::Unsupported)
    }
}
