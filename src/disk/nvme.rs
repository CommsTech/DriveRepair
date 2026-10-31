// NVMe disk interface via PCIe
// Gate 0: fail-closed — detect and I/O return Unsupported

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// NVMe controller structure
pub struct NvmeController {
    base_address: u64,
    namespace_count: u32,
}

/// NVMe disk implementation
pub struct NvmeDisk {
    controller: NvmeController,
    namespace_id: u32,
    sector_size: u64,
    total_sectors: u64,
    #[cfg(feature = "alloc")]
    model: String,
    #[cfg(feature = "alloc")]
    serial: String,
    #[cfg(feature = "alloc")]
    firmware: String,
}

impl NvmeController {
    /// Detect and initialize NVMe controller
    pub fn detect() -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: NVMe PCI enumeration and init not implemented
        Err(DiskError::Unsupported)
    }

    /// Get number of namespaces
    pub fn namespace_count(&self) -> u32 {
        self.namespace_count
    }
}

impl NvmeDisk {
    /// Create new NVMe disk instance
    ///
    /// # Arguments
    /// * `controller` - NVMe controller instance
    /// * `namespace_id` - Namespace ID (typically 1)
    pub fn new(controller: NvmeController, namespace_id: u32) -> Result<Self, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: NVMe namespace identify not implemented
        Ok(Self {
            controller,
            namespace_id,
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

    /// Submit NVMe command
    #[allow(dead_code)]
    fn submit_command(&self, _opcode: u8, _nsid: u32, _data: &[u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: NVMe command submission not implemented
        Err(DiskError::Unsupported)
    }

    #[allow(dead_code)]
    fn send_command(&self, _opcode: u8, _nsid: u32, _data: &[u8]) -> Result<(), DiskError> {
        self.submit_command(_opcode, _nsid, _data)
    }

    #[allow(dead_code)]
    fn wait_ready(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: NVMe controller ready wait not implemented
        Err(DiskError::Unsupported)
    }
}

impl Disk for NvmeDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(DiskInfo {
            interface: DiskInterface::NVMe,
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
        // EXPERIMENTAL/UNSUPPORTED: NVMe READ not implemented
        Err(DiskError::Unsupported)
    }

    fn write_sectors(&self, _lba: u64, _count: u32, _buffer: &[u8]) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: NVMe WRITE not implemented
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
        // EXPERIMENTAL/UNSUPPORTED: NVMe FLUSH not implemented
        Err(DiskError::Unsupported)
    }
}
