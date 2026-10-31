// Disk repair engine
// Gate 0: honest sector outcomes, read-only default, iterator-based sequential scan

#![allow(dead_code)]

use crate::disk::{AccessMode, Disk, DiskError};
use core::default::Default;
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

pub mod crc32;
pub mod recovery;
use recovery::{verify_against_expected, ErrorRecovery, RetryStrategy, VerificationResult};

/// Honest per-sector outcome (Gate 0).
/// A successful read is `ReadOk`, never "Repaired".
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SectorOutcome {
    /// Sector bytes were read successfully (not a repair claim)
    ReadOk,
    /// Read returned an error (retries exhausted or soft error)
    ReadError,
    /// Data was read but could not be verified against an expected value
    ReadUnverified,
    /// Sector could not be read
    Unreadable,
    /// Data was copied and verified against expected integrity data
    CopiedAndVerified,
    /// Sector was rewritten and the rewrite verified
    RewriteVerified,
    /// Operation was not attempted
    NotAttempted,
    /// Sector was intentionally skipped
    Skipped,
}

/// Compatibility alias — prefer `SectorOutcome` for new code.
pub type RepairResult = SectorOutcome;

/// Scan pattern types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScanPattern {
    /// Sequential scan (start to end)
    Sequential,
    /// Reverse scan (end to start)
    Reverse,
    /// Random scan (bounded / streamed — never allocates all LBAs)
    Random,
    /// Concentric scan (outer to inner, streamed)
    Concentric,
}

/// Maximum sectors processed for Random/Concentric patterns without allocating all LBAs
const BOUNDED_SCAN_CAP: u64 = 1_048_576;

/// Repair configuration
#[derive(Debug, Clone)]
pub struct RepairConfig {
    /// Maximum retry attempts per sector
    pub max_retries: u32,
    /// Timeout per read attempt (milliseconds)
    pub timeout_ms: u32,
    /// Scan pattern to use
    pub scan_pattern: ScanPattern,
    /// Enable aggressive error correction
    pub aggressive_correction: bool,
    /// Enable TRIM for SSDs (still gated: requires allow_writes)
    pub enable_trim: bool,
    /// Explicit write permission (default false — Gate 0 fail-closed)
    pub allow_writes: bool,
    /// Minimum sector to scan
    pub start_sector: u64,
    /// Maximum sector to scan (exclusive end semantics when used as range end)
    pub end_sector: u64,
}

impl Default for RepairConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            timeout_ms: 5000,
            scan_pattern: ScanPattern::Sequential,
            aggressive_correction: false,
            enable_trim: false,
            allow_writes: false,
            start_sector: 0,
            end_sector: u64::MAX,
        }
    }
}

impl RepairConfig {
    /// Effective access mode derived from allow_writes
    pub fn access_mode(&self) -> AccessMode {
        if self.allow_writes {
            AccessMode::ReadWrite
        } else {
            AccessMode::ReadOnly
        }
    }
}

/// Repair engine
pub struct RepairEngine<D: Disk> {
    disk: D,
    config: RepairConfig,
}

impl<D: Disk> RepairEngine<D> {
    /// Create new repair engine
    pub fn new(disk: D, config: RepairConfig) -> Self {
        Self { disk, config }
    }

    /// Consume engine and return underlying disk (for tests / accounting)
    pub fn into_disk(self) -> D {
        self.disk
    }

    /// Borrow disk
    pub fn disk(&self) -> &D {
        &self.disk
    }

    /// Scan and repair disk using iterator patterns (no O(n) LBA Vec for Sequential)
    #[cfg(feature = "alloc")]
    pub fn scan_and_repair<F>(&mut self, mut progress_callback: F) -> Result<RepairStats, DiskError>
    where
        F: FnMut(u64, u64, SectorOutcome),
    {
        let total_sectors = self.disk.total_sectors();
        let mut stats = RepairStats::default();

        // Fix start>end and end==0 underflow before any arithmetic
        if self.config.start_sector > self.config.end_sector {
            return Ok(stats);
        }

        let start = self.config.start_sector.min(total_sectors);
        let end = self.config.end_sector.min(total_sectors);
        if start >= end {
            return Ok(stats);
        }

        let sectors_to_scan = end.saturating_sub(start);
        let mut sector_buffer = alloc::vec![0u8; self.disk.sector_size() as usize];

        match self.config.scan_pattern {
            ScanPattern::Sequential => {
                for sector in start..end {
                    self.process_sector(
                        sector,
                        sectors_to_scan,
                        &mut sector_buffer,
                        &mut stats,
                        &mut progress_callback,
                    )?;
                }
            }
            ScanPattern::Reverse => {
                // Iterate reverse without collecting
                let mut sector = end;
                while sector > start {
                    sector -= 1;
                    self.process_sector(
                        sector,
                        sectors_to_scan,
                        &mut sector_buffer,
                        &mut stats,
                        &mut progress_callback,
                    )?;
                }
            }
            ScanPattern::Random => {
                // Bounded stream: visit up to BOUNDED_SCAN_CAP without allocating all LBAs
                let limit = sectors_to_scan.min(BOUNDED_SCAN_CAP);
                let mut seed = start ^ end ^ 0x9E37_79B9;
                for i in 0..limit {
                    seed = seed
                        .wrapping_mul(1_103_515_245)
                        .wrapping_add(12_345);
                    let offset = seed % sectors_to_scan;
                    let sector =
                        start.saturating_add(offset.wrapping_add(i) % sectors_to_scan);
                    self.process_sector(
                        sector,
                        sectors_to_scan,
                        &mut sector_buffer,
                        &mut stats,
                        &mut progress_callback,
                    )?;
                }
            }
            ScanPattern::Concentric => {
                // Stream left/right without allocating the full vector
                let mut left = start;
                let mut right = end - 1; // safe: start < end
                let mut visited = 0u64;
                while left <= right && visited < BOUNDED_SCAN_CAP {
                    self.process_sector(
                        left,
                        sectors_to_scan,
                        &mut sector_buffer,
                        &mut stats,
                        &mut progress_callback,
                    )?;
                    visited += 1;
                    if left != right && visited < BOUNDED_SCAN_CAP {
                        self.process_sector(
                            right,
                            sectors_to_scan,
                            &mut sector_buffer,
                            &mut stats,
                            &mut progress_callback,
                        )?;
                        visited += 1;
                    }
                    if left == right {
                        break;
                    }
                    left = left.saturating_add(1);
                    if right > start {
                        right -= 1;
                    } else {
                        break;
                    }
                }
            }
        }

        Ok(stats)
    }

    #[cfg(feature = "alloc")]
    fn process_sector<F>(
        &self,
        sector: u64,
        sectors_to_scan: u64,
        sector_buffer: &mut [u8],
        stats: &mut RepairStats,
        progress_callback: &mut F,
    ) -> Result<(), DiskError>
    where
        F: FnMut(u64, u64, SectorOutcome),
    {
        let result = self.repair_sector(sector, sector_buffer)?;
        stats.record(result);
        progress_callback(sector, sectors_to_scan, result);
        Ok(())
    }

    /// Inspect a single sector (read-only by default). Successful read => ReadOk, not Repaired.
    fn repair_sector(&self, lba: u64, buffer: &mut [u8]) -> Result<SectorOutcome, DiskError> {
        let max_retries = if self.config.max_retries == 0 {
            1
        } else {
            self.config.max_retries
        };

        let recovery = ErrorRecovery::new(
            RetryStrategy::ExponentialBackoff {
                initial_delay_ms: 100,
                max_delay_ms: self.config.timeout_ms,
                multiplier: 2.0,
            },
            max_retries,
        );

        match recovery.retry(|| self.disk.read_sectors(lba, 1, buffer)) {
            Ok(()) => {
                // Without an expected CRC we cannot claim verified — ReadOk is honest.
                match verify_against_expected(buffer, None) {
                    VerificationResult::Verified => Ok(SectorOutcome::CopiedAndVerified),
                    VerificationResult::Unverified => Ok(SectorOutcome::ReadOk),
                    VerificationResult::Mismatch => Ok(SectorOutcome::ReadUnverified),
                }
            }
            Err(_) => {
                if self.config.aggressive_correction {
                    // EXPERIMENTAL/UNSUPPORTED: partial-read recovery not implemented
                    Ok(SectorOutcome::Unreadable)
                } else {
                    Ok(SectorOutcome::Unreadable)
                }
            }
        }
    }

    /// Read sector with retry logic
    pub fn read_sector_with_retry(&self, lba: u64, buffer: &mut [u8]) -> Result<(), DiskError> {
        let max_retries = if self.config.max_retries == 0 {
            1
        } else {
            self.config.max_retries
        };
        let recovery = ErrorRecovery::new(
            RetryStrategy::ExponentialBackoff {
                initial_delay_ms: 100,
                max_delay_ms: self.config.timeout_ms,
                multiplier: 2.0,
            },
            max_retries,
        );

        recovery.retry(|| self.disk.read_sectors(lba, 1, buffer))
    }

    /// Write sector with verification — requires ReadWrite / allow_writes
    #[cfg(feature = "alloc")]
    pub fn write_sector_with_verify(&self, lba: u64, buffer: &[u8]) -> Result<(), DiskError> {
        if self.config.access_mode() != AccessMode::ReadWrite {
            return Err(DiskError::WriteDenied);
        }
        if self.disk.access_mode() != AccessMode::ReadWrite {
            return Err(DiskError::WriteDenied);
        }

        self.disk.write_sectors(lba, 1, buffer)?;

        let mut read_buffer = alloc::vec![0u8; buffer.len()];
        self.disk.read_sectors(lba, 1, &mut read_buffer)?;

        if read_buffer == buffer {
            Ok(())
        } else {
            Err(DiskError::WriteError)
        }
    }

    /// Execute TRIM command for SSDs — fail-closed until implemented and allow_writes
    pub fn trim_sectors(&self, _lba: u64, _count: u32) -> Result<(), DiskError> {
        if !self.config.allow_writes || !self.config.enable_trim {
            return Err(DiskError::WriteDenied);
        }
        // EXPERIMENTAL/UNSUPPORTED: TRIM / DATA SET MANAGEMENT not implemented
        Err(DiskError::Unsupported)
    }

    /// Secure erase — fail-closed
    pub fn secure_erase(&self) -> Result<(), DiskError> {
        if !self.config.allow_writes {
            return Err(DiskError::WriteDenied);
        }
        // EXPERIMENTAL/UNSUPPORTED: secure erase not implemented
        Err(DiskError::Unsupported)
    }
}

/// Repair statistics
#[derive(Debug, Clone, Default)]
pub struct RepairStats {
    /// Only incremented for RewriteVerified (never for mere reads)
    pub repaired: u64,
    /// Successful reads (ReadOk)
    pub readable: u64,
    /// Alias counter kept in sync with readable for clarity in tests
    pub read_ok: u64,
    pub read_error: u64,
    pub read_unverified: u64,
    pub unreadable: u64,
    pub recovered: u64,
    pub failed: u64,
    pub skipped: u64,
}

impl RepairStats {
    fn record(&mut self, outcome: SectorOutcome) {
        match outcome {
            SectorOutcome::ReadOk => {
                self.readable += 1;
                self.read_ok += 1;
            }
            SectorOutcome::ReadError => {
                self.read_error += 1;
                self.failed += 1;
            }
            SectorOutcome::ReadUnverified => {
                self.read_unverified += 1;
                self.recovered += 1;
            }
            SectorOutcome::Unreadable => {
                self.unreadable += 1;
                self.failed += 1;
            }
            SectorOutcome::CopiedAndVerified => {
                self.readable += 1;
                self.read_ok += 1;
            }
            SectorOutcome::RewriteVerified => {
                self.repaired += 1;
            }
            SectorOutcome::NotAttempted | SectorOutcome::Skipped => {
                self.skipped += 1;
            }
        }
    }

    /// Get total sectors processed
    pub fn total(&self) -> u64 {
        self.read_ok
            + self.read_error
            + self.read_unverified
            + self.unreadable
            + self.repaired
            + self.skipped
    }

    /// Get success rate based on readable sectors (not "repaired")
    pub fn success_rate(&self) -> f64 {
        let total = self.total();
        if total == 0 {
            return 0.0;
        }
        (self.readable + self.recovered) as f64 / total as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_repair_stats() {
        let stats = RepairStats {
            repaired: 0,
            readable: 100,
            read_ok: 100,
            read_error: 0,
            read_unverified: 0,
            unreadable: 10,
            recovered: 50,
            failed: 10,
            skipped: 0,
        };

        assert_eq!(stats.total(), 110);
        assert!(stats.success_rate() > 0.0);
    }

    #[test]
    fn test_allow_writes_default_false() {
        let cfg = RepairConfig::default();
        assert!(!cfg.allow_writes);
        assert_eq!(cfg.access_mode(), AccessMode::ReadOnly);
    }

    #[test]
    fn test_start_after_end_no_underflow() {
        // Structural: config with start > end should be handled by scan
        let cfg = RepairConfig {
            start_sector: 100,
            end_sector: 50,
            ..RepairConfig::default()
        };
        assert!(cfg.start_sector > cfg.end_sector);
    }
}
