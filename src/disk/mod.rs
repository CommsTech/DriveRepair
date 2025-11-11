// Unified disk interface trait
// Supports ATA, SATA, NVMe, and USB drives with 64-bit LBA addressing

#![allow(dead_code)]

use core::marker::{Send, Sync};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod ata;
pub mod ata_port_io;
pub mod detection;
#[cfg(feature = "alloc")]
pub mod enhanced_detection;
pub mod nvme;
pub mod sata;
pub mod usb;
pub mod utils;

/// Sector size constants
pub const SECTOR_SIZE_512: u64 = 512;
pub const SECTOR_SIZE_4096: u64 = 4096;

/// Disk interface types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DiskInterface {
    ATA,
    SATA,
    NVMe,
    USB,
}

/// Disk information structure
#[derive(Debug, Clone)]
pub struct DiskInfo {
    pub interface: DiskInterface,
    pub size_bytes: u64,
    pub sector_size: u64,
    pub total_sectors: u64,
    #[cfg(feature = "alloc")]
    pub model: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub model: &'static str,
    #[cfg(feature = "alloc")]
    pub serial: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub serial: &'static str,
    #[cfg(feature = "alloc")]
    pub firmware: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub firmware: &'static str,
}

/// Error types for disk operations
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DiskError {
    /// Sector read error
    ReadError,
    /// Sector write error
    WriteError,
    /// Invalid sector address
    InvalidSector,
    /// Invalid parameter
    InvalidParameter,
    /// Drive not ready
    NotReady,
    /// Timeout
    Timeout,
    /// Unsupported operation
    Unsupported,
    /// Hardware error
    HardwareError,
    /// Read-only media
    ReadOnly,
}

/// Unified disk trait for all interface types
pub trait Disk: Send + Sync {
    /// Get disk information
    fn info(&self) -> Result<DiskInfo, DiskError>;

    /// Read sectors from disk using 64-bit LBA
    ///
    /// # Arguments
    /// * `lba` - Starting Logical Block Address (64-bit)
    /// * `count` - Number of sectors to read
    /// * `buffer` - Buffer to store read data (must be at least count * sector_size bytes)
    fn read_sectors(&self, lba: u64, count: u32, buffer: &mut [u8]) -> Result<(), DiskError>;

    /// Write sectors to disk using 64-bit LBA
    ///
    /// # Arguments
    /// * `lba` - Starting Logical Block Address (64-bit)
    /// * `count` - Number of sectors to write
    /// * `buffer` - Buffer containing data to write (must be at least count * sector_size bytes)
    fn write_sectors(&self, lba: u64, count: u32, buffer: &[u8]) -> Result<(), DiskError>;

    /// Get sector size for this disk
    fn sector_size(&self) -> u64;

    /// Get total number of sectors (64-bit)
    fn total_sectors(&self) -> u64;

    /// Get disk size in bytes (64-bit)
    fn size_bytes(&self) -> u64 {
        self.total_sectors() * self.sector_size()
    }

    /// Check if disk is ready
    fn is_ready(&self) -> bool;

    /// Flush any pending writes
    fn flush(&self) -> Result<(), DiskError>;
}

/// Helper function to calculate LBA from CHS (for compatibility)
/// Note: This is for reference only - modern implementation uses 64-bit LBA directly
#[allow(dead_code)]
pub fn chs_to_lba(
    cylinder: u32,
    head: u32,
    sector: u32,
    heads_per_cylinder: u32,
    sectors_per_track: u32,
) -> u64 {
    ((cylinder as u64 * heads_per_cylinder as u64 + head as u64) * sectors_per_track as u64
        + sector as u64)
        - 1
}

/// Helper function to validate LBA address
pub fn validate_lba(lba: u64, total_sectors: u64) -> bool {
    lba < total_sectors
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chs_to_lba() {
        // Test CHS to LBA conversion
        let lba = chs_to_lba(0, 0, 1, 255, 63);
        assert_eq!(lba, 0);
    }

    #[test]
    fn test_validate_lba() {
        assert!(validate_lba(0, 1000));
        assert!(validate_lba(999, 1000));
        assert!(!validate_lba(1000, 1000));
    }
}
