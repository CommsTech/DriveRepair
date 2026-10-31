// Unified disk interface trait
// Supports ATA, SATA, NVMe, and USB drives with 64-bit LBA addressing
// Gate 0: fail-closed stubs, identity helpers, mock disk for safety tests

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

#[cfg(feature = "alloc")]
pub mod mock;

#[cfg(all(test, feature = "alloc"))]
pub use mock::MockDisk;

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
    /// Interface could not be determined (fail-closed / unknown path)
    Unknown,
}

/// Access mode for disk operations (Gate 0: default read-only)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AccessMode {
    /// Reads allowed; all writes denied
    #[default]
    ReadOnly,
    /// Reads and writes allowed (explicit opt-in only)
    ReadWrite,
}

impl AccessMode {
    /// Returns true if write operations are permitted
    pub fn allows_writes(self) -> bool {
        matches!(self, AccessMode::ReadWrite)
    }
}

/// Stable device identity used to reject source==destination mistakes
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeviceIdentity {
    #[cfg(feature = "alloc")]
    pub path: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub path: &'static str,
    #[cfg(feature = "alloc")]
    pub serial: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub serial: &'static str,
    #[cfg(feature = "alloc")]
    pub model: alloc::string::String,
    #[cfg(not(feature = "alloc"))]
    pub model: &'static str,
}

impl DeviceIdentity {
    /// Create identity from path and serial (alloc)
    #[cfg(feature = "alloc")]
    pub fn new(
        path: impl Into<alloc::string::String>,
        serial: impl Into<alloc::string::String>,
        model: impl Into<alloc::string::String>,
    ) -> Self {
        Self {
            path: path.into(),
            serial: serial.into(),
            model: model.into(),
        }
    }

    /// True when identity fields are empty / unknown
    pub fn is_unknown(&self) -> bool {
        self.path.is_empty() && self.serial.is_empty()
    }

    /// True when two identities refer to the same device (path or serial)
    pub fn conflicts_with(&self, other: &DeviceIdentity) -> bool {
        if self.is_unknown() || other.is_unknown() {
            return false;
        }
        (!self.path.is_empty() && self.path == other.path)
            || (!self.serial.is_empty() && self.serial == other.serial)
    }
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
    /// Write rejected by access policy (read-only mode / Gate 0)
    WriteDenied,
    /// Device identity could not be established
    IdentityUnknown,
    /// Source and destination refer to the same device
    SourceDestinationConflict,
    /// Backend or device temporarily / permanently unavailable
    Unavailable,
    /// Invalid sector address
    InvalidSector,
    /// Invalid parameter
    InvalidParameter,
    /// Drive not ready
    NotReady,
    /// Timeout
    Timeout,
    /// Unsupported operation (unimplemented / experimental backend)
    Unsupported,
    /// Hardware error
    HardwareError,
    /// Read-only media
    ReadOnly,
}

impl Default for DiskError {
    fn default() -> Self {
        DiskError::Unsupported
    }
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

    /// Get disk size in bytes (64-bit) using checked multiplication
    fn size_bytes(&self) -> u64 {
        self.total_sectors()
            .checked_mul(self.sector_size())
            .unwrap_or(u64::MAX)
    }

    /// Check if disk is ready
    fn is_ready(&self) -> bool;

    /// Flush any pending writes
    fn flush(&self) -> Result<(), DiskError>;

    /// Optional access mode (defaults to ReadOnly for safety)
    fn access_mode(&self) -> AccessMode {
        AccessMode::ReadOnly
    }
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
        let lba = chs_to_lba(0, 0, 1, 255, 63);
        assert_eq!(lba, 0);
    }

    #[test]
    fn test_validate_lba() {
        assert!(validate_lba(0, 1000));
        assert!(validate_lba(999, 1000));
        assert!(!validate_lba(1000, 1000));
    }

    #[test]
    fn test_access_mode_default_readonly() {
        assert_eq!(AccessMode::default(), AccessMode::ReadOnly);
        assert!(!AccessMode::ReadOnly.allows_writes());
        assert!(AccessMode::ReadWrite.allows_writes());
    }

    #[cfg(feature = "alloc")]
    #[test]
    fn test_device_identity_conflict() {
        let a = DeviceIdentity::new("/dev/sda", "SERIAL1", "Model");
        let b = DeviceIdentity::new("/dev/sda", "OTHER", "Model");
        let c = DeviceIdentity::new("/dev/sdb", "SERIAL1", "Model");
        let d = DeviceIdentity::new("/dev/sdc", "SERIAL2", "Model");
        assert!(a.conflicts_with(&b));
        assert!(a.conflicts_with(&c));
        assert!(!a.conflicts_with(&d));
    }
}
