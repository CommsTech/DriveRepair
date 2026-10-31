// Mock disk for Gate 0 safety unit tests
// Tracks read/write counts and supports injected errors — never touches real hardware

#![cfg(feature = "alloc")]

use crate::disk::{AccessMode, Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};
use alloc::vec::Vec;
use core::cell::UnsafeCell;
use core::result::Result;
use core::sync::atomic::{AtomicU64, Ordering};

/// In-memory mock disk used by safety tests.
/// Sparse mode avoids allocating backing store for huge sector counts (iterator OOM tests).
pub struct MockDisk {
    sector_size: u64,
    total_sectors: u64,
    /// When None, reads fill zeros without a backing store (sparse)
    data: UnsafeCell<Option<Vec<u8>>>,
    access_mode: AccessMode,
    pub read_count: AtomicU64,
    pub write_count: AtomicU64,
    pub flush_count: AtomicU64,
    inject_read_error: bool,
    inject_write_error: bool,
}

// Single-threaded unit-test mock; counters are atomic, data guarded by test discipline
unsafe impl Sync for MockDisk {}
unsafe impl Send for MockDisk {}

impl MockDisk {
    /// Create a mock disk with backing store (suitable for small disks)
    pub fn new(total_sectors: u64) -> Self {
        let sector_size = SECTOR_SIZE_512;
        let len = (total_sectors.checked_mul(sector_size).unwrap_or(0)) as usize;
        Self {
            sector_size,
            total_sectors,
            data: UnsafeCell::new(Some(alloc::vec![0u8; len])),
            access_mode: AccessMode::ReadOnly,
            read_count: AtomicU64::new(0),
            write_count: AtomicU64::new(0),
            flush_count: AtomicU64::new(0),
            inject_read_error: false,
            inject_write_error: false,
        }
    }

    /// Create a sparse mock (no O(n) backing store) for large-range scan tests
    pub fn new_sparse(total_sectors: u64) -> Self {
        Self {
            sector_size: SECTOR_SIZE_512,
            total_sectors,
            data: UnsafeCell::new(None),
            access_mode: AccessMode::ReadOnly,
            read_count: AtomicU64::new(0),
            write_count: AtomicU64::new(0),
            flush_count: AtomicU64::new(0),
            inject_read_error: false,
            inject_write_error: false,
        }
    }

    /// Create a mock disk that allows writes
    pub fn new_read_write(total_sectors: u64) -> Self {
        let mut disk = Self::new(total_sectors);
        disk.access_mode = AccessMode::ReadWrite;
        disk
    }

    /// Force reads to fail
    pub fn inject_read_error(&mut self, enabled: bool) {
        self.inject_read_error = enabled;
    }

    /// Force writes to fail
    pub fn inject_write_error(&mut self, enabled: bool) {
        self.inject_write_error = enabled;
    }

    /// Set access mode explicitly
    pub fn set_access_mode(&mut self, mode: AccessMode) {
        self.access_mode = mode;
    }

    fn validate_range(&self, lba: u64, count: u32) -> Result<(usize, usize), DiskError> {
        if !self.is_ready() {
            return Err(DiskError::NotReady);
        }
        let end = lba
            .checked_add(count as u64)
            .ok_or(DiskError::InvalidSector)?;
        if end > self.total_sectors {
            return Err(DiskError::InvalidSector);
        }
        let start_byte = (lba
            .checked_mul(self.sector_size)
            .ok_or(DiskError::InvalidSector)?) as usize;
        let len = (count as u64)
            .checked_mul(self.sector_size)
            .ok_or(DiskError::InvalidSector)? as usize;
        Ok((start_byte, len))
    }
}

impl Disk for MockDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(DiskInfo {
            interface: DiskInterface::Unknown,
            size_bytes: self.size_bytes(),
            sector_size: self.sector_size,
            total_sectors: self.total_sectors,
            model: alloc::string::String::from("MockDisk"),
            serial: alloc::string::String::from("MOCK-SERIAL"),
            firmware: alloc::string::String::from("0.0.1"),
        })
    }

    fn read_sectors(&self, lba: u64, count: u32, buffer: &mut [u8]) -> Result<(), DiskError> {
        if self.inject_read_error {
            return Err(DiskError::ReadError);
        }
        let (start, len) = self.validate_range(lba, count)?;
        if buffer.len() < len {
            return Err(DiskError::InvalidParameter);
        }
        unsafe {
            match &*self.data.get() {
                Some(data) => buffer[..len].copy_from_slice(&data[start..start + len]),
                None => buffer[..len].fill(0),
            }
        }
        self.read_count.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    fn write_sectors(&self, lba: u64, count: u32, buffer: &[u8]) -> Result<(), DiskError> {
        if !self.access_mode.allows_writes() {
            return Err(DiskError::WriteDenied);
        }
        if self.inject_write_error {
            return Err(DiskError::WriteError);
        }
        let (start, len) = self.validate_range(lba, count)?;
        if buffer.len() < len {
            return Err(DiskError::InvalidParameter);
        }
        unsafe {
            if let Some(data) = &mut *self.data.get() {
                data[start..start + len].copy_from_slice(&buffer[..len]);
            }
        }
        self.write_count.fetch_add(1, Ordering::Relaxed);
        Ok(())
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
        if !self.access_mode.allows_writes() {
            return Err(DiskError::WriteDenied);
        }
        self.flush_count.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    fn access_mode(&self) -> AccessMode {
        self.access_mode
    }
}

#[cfg(test)]
mod safety_tests {
    use super::*;
    use crate::disk::ata::AtaDisk;
    use crate::disk::nvme::NvmeController;
    use crate::disk::sata::AhciController;
    use crate::disk::usb::UsbDisk;
    use crate::repair::recovery::{ErrorRecovery, RetryStrategy};
    use crate::repair::{RepairConfig, RepairEngine, SectorOutcome};
    use crate::smart::SmartParser;

    #[test]
    fn unimplemented_ata_read_write_unsupported() {
        let disk = AtaDisk::new(true, true).expect("construct stub");
        assert!(!disk.is_ready());
        let mut buf = [0u8; 512];
        assert_eq!(
            disk.read_sectors(0, 1, &mut buf),
            Err(DiskError::Unsupported)
        );
        assert_eq!(disk.write_sectors(0, 1, &buf), Err(DiskError::Unsupported));
        assert_eq!(disk.flush(), Err(DiskError::Unsupported));
    }

    #[test]
    fn unimplemented_ahci_nvme_detect_unsupported() {
        assert!(matches!(
            AhciController::detect(),
            Err(DiskError::Unsupported)
        ));
        assert!(matches!(
            NvmeController::detect(),
            Err(DiskError::Unsupported)
        ));
    }

    #[test]
    fn unimplemented_usb_read_write_unsupported() {
        let disk = UsbDisk::new(1).expect("construct stub");
        assert!(!disk.is_ready());
        let mut buf = [0u8; 512];
        assert_eq!(
            disk.read_sectors(0, 1, &mut buf),
            Err(DiskError::Unsupported)
        );
        assert_eq!(disk.write_sectors(0, 1, &buf), Err(DiskError::Unsupported));
    }

    #[test]
    fn empty_smart_attributes_unknown_not_healthy() {
        let status = SmartParser::interpret_health(&[]);
        assert_eq!(status, crate::smart::SmartHealthStatus::Unknown);
        assert_ne!(status, crate::smart::SmartHealthStatus::Healthy);
    }

    #[test]
    fn readonly_mode_rejects_writes() {
        let disk = MockDisk::new(16);
        assert_eq!(disk.access_mode(), AccessMode::ReadOnly);
        let buf = [0u8; 512];
        assert_eq!(disk.write_sectors(0, 1, &buf), Err(DiskError::WriteDenied));
        assert_eq!(disk.write_count.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn mock_scan_does_not_call_write() {
        let disk = MockDisk::new(64);
        let config = RepairConfig {
            start_sector: 0,
            end_sector: 32,
            allow_writes: false,
            ..RepairConfig::default()
        };
        let mut engine = RepairEngine::new(disk, config);
        let stats = engine
            .scan_and_repair(|_lba, _total, _outcome| {})
            .expect("scan");
        assert_eq!(stats.repaired, 0);
        let disk_after = engine.into_disk();
        assert_eq!(disk_after.write_count.load(Ordering::Relaxed), 0);
        assert!(disk_after.read_count.load(Ordering::Relaxed) > 0);
    }

    #[test]
    fn sequential_large_range_does_not_oom() {
        let disk = MockDisk::new_sparse(1_000_001);
        let config = RepairConfig {
            start_sector: 0,
            end_sector: 1_000_000,
            max_retries: 1,
            allow_writes: false,
            ..RepairConfig::default()
        };
        let mut engine = RepairEngine::new(disk, config);
        let mut seen = 0u64;
        let stats = engine
            .scan_and_repair(|_lba, _total, outcome| {
                seen += 1;
                assert!(matches!(
                    outcome,
                    SectorOutcome::ReadOk
                        | SectorOutcome::ReadUnverified
                        | SectorOutcome::Skipped
                        | SectorOutcome::Unreadable
                        | SectorOutcome::ReadError
                        | SectorOutcome::NotAttempted
                ));
            })
            .expect("large sequential scan");
        assert_eq!(seen, 1_000_000);
        assert_eq!(stats.repaired, 0);
        assert_eq!(engine.into_disk().write_count.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn max_attempts_zero_does_not_panic() {
        let recovery = ErrorRecovery::new(RetryStrategy::None, 0);
        let result: Result<(), DiskError> = recovery.retry(|| Err(DiskError::ReadError));
        assert_eq!(result, Err(DiskError::Unsupported));
        let result_ok: Result<(), DiskError> = recovery.retry(|| Ok(()));
        assert_eq!(result_ok, Err(DiskError::Unsupported));
    }
}
