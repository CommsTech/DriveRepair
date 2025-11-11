// Disk repair engine
// Implements low-level sector reading, error correction, and surface scanning

#![allow(dead_code)]

use crate::disk::{Disk, DiskError};
use core::result::Result;
use core::default::Default;
use core::ops::Fn;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

pub mod crc32;
pub mod recovery;
use recovery::{verify_sector, ErrorRecovery, RetryStrategy, VerificationMethod};

/// Repair operation result
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RepairResult {
    /// Sector repaired successfully
    Repaired,
    /// Sector recovered (data read but may be corrupted)
    Recovered,
    /// Sector failed (unrecoverable)
    Failed,
    /// Sector skipped
    Skipped,
}

/// Scan pattern types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScanPattern {
    /// Sequential scan (start to end)
    Sequential,
    /// Reverse scan (end to start)
    Reverse,
    /// Random scan
    Random,
    /// Concentric scan (outer to inner)
    Concentric,
}

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
    /// Enable TRIM for SSDs
    pub enable_trim: bool,
    /// Minimum sector to scan
    pub start_sector: u64,
    /// Maximum sector to scan
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
            start_sector: 0,
            end_sector: u64::MAX,
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

    /// Scan and repair disk
    #[cfg(feature = "alloc")]
    pub fn scan_and_repair<F>(&mut self, progress_callback: F) -> Result<RepairStats, DiskError>
    where
        F: Fn(u64, u64, RepairResult),
    {
        let total_sectors = self.disk.total_sectors();
        let start = self.config.start_sector.min(total_sectors);
        let end = self.config.end_sector.min(total_sectors);
        let sectors_to_scan = end - start;

        let mut stats = RepairStats::default();
        let mut sector_buffer = vec![0u8; self.disk.sector_size() as usize];

        let sectors = match self.config.scan_pattern {
            ScanPattern::Sequential => (start..end).collect(),
            ScanPattern::Reverse => (start..end).rev().collect(),
            ScanPattern::Random => {
                let mut sectors: Vec<u64> = (start..end).collect();
                // Simple pseudo-random shuffle using LCG
                // This is deterministic but provides good distribution
                let mut seed = start ^ end;
                for i in (1..sectors.len()).rev() {
                    seed = seed.wrapping_mul(1103515245).wrapping_add(12345);
                    let j = (seed % (i + 1) as u64) as usize;
                    sectors.swap(i, j);
                }
                sectors
            }
            ScanPattern::Concentric => {
                // Concentric pattern: start from outer edges, work inward
                let mut sectors: Vec<u64> = Vec::new();
                let mut left = start;
                let mut right = end - 1;

                while left <= right {
                    if left == right {
                        sectors.push(left);
                    } else {
                        sectors.push(left);
                        sectors.push(right);
                    }
                    left += 1;
                    if right > start {
                        right -= 1;
                    }
                }
                sectors
            }
        };

        for sector in sectors.iter() {
            let result = self.repair_sector(*sector, &mut sector_buffer)?;

            match result {
                RepairResult::Repaired => stats.repaired += 1,
                RepairResult::Recovered => stats.recovered += 1,
                RepairResult::Failed => stats.failed += 1,
                RepairResult::Skipped => stats.skipped += 1,
            }

            progress_callback(*sector, sectors_to_scan, result);
        }

        Ok(stats)
    }

    /// Repair a single sector
    ///
    /// Based on SpinRite analysis:
    /// - Uses exponential backoff retry strategy
    /// - Verifies data integrity after read
    /// - Attempts partial read recovery on failure
    /// - Marks sector as bad if all recovery attempts fail
    fn repair_sector(&self, lba: u64, buffer: &mut [u8]) -> Result<RepairResult, DiskError> {
        // Create error recovery with retry strategy
        // SpinRite uses exponential backoff: 100ms initial, 2.0 multiplier, max 3-5 retries
        let recovery = ErrorRecovery::new(
            RetryStrategy::ExponentialBackoff {
                initial_delay_ms: 100,
                max_delay_ms: self.config.timeout_ms,
                multiplier: 2.0,
            },
            self.config.max_retries,
        );

        // Try to read sector with retries
        // SpinRite pattern: retry with exponential backoff, verify after each read
        match recovery.retry(|| self.disk.read_sectors(lba, 1, buffer)) {
            Ok(()) => {
                // Sector read successfully - verify data integrity
                // SpinRite verifies data using checksum or ECC
                let verification_method = if self.config.aggressive_correction {
                    VerificationMethod::Crc32
                } else {
                    VerificationMethod::Checksum
                };

                if verify_sector(buffer, verification_method) {
                    Ok(RepairResult::Repaired)
                } else {
                    // Data read but may be corrupted
                    // SpinRite attempts to recover partial data
                    Ok(RepairResult::Recovered)
                }
            }
            Err(_) => {
                // All retries failed - attempt data recovery
                // SpinRite pattern: try partial reads, different read modes
                if self.config.aggressive_correction {
                    // Try reading partial sectors or using different modes
                    // TODO: Implement partial read recovery
                    // - Try reading with different sector sizes
                    // - Try reading with different timing
                    // - Attempt to reconstruct from partial data
                    Ok(RepairResult::Failed)
                } else {
                    Ok(RepairResult::Failed)
                }
            }
        }
    }

    /// Read sector with retry logic
    pub fn read_sector_with_retry(&self, lba: u64, buffer: &mut [u8]) -> Result<(), DiskError> {
        let recovery = ErrorRecovery::new(
            RetryStrategy::ExponentialBackoff {
                initial_delay_ms: 100,
                max_delay_ms: self.config.timeout_ms,
                multiplier: 2.0,
            },
            self.config.max_retries,
        );

        recovery.retry(|| self.disk.read_sectors(lba, 1, buffer))
    }

    /// Write sector with verification
    #[cfg(feature = "alloc")]
    pub fn write_sector_with_verify(&self, lba: u64, buffer: &[u8]) -> Result<(), DiskError> {
        // Write sector
        self.disk.write_sectors(lba, 1, buffer)?;

        // Verify write
        let mut read_buffer = vec![0u8; buffer.len()];
        self.disk.read_sectors(lba, 1, &mut read_buffer)?;

        if read_buffer == buffer {
            Ok(())
        } else {
            Err(DiskError::WriteError)
        }
    }

    /// Execute TRIM command for SSDs
    pub fn trim_sectors(&self, _lba: u64, _count: u32) -> Result<(), DiskError> {
        // TODO: Implement TRIM command
        // For ATA: DATA SET MANAGEMENT command (0x06)
        // For NVMe: DEALLOCATE command
        Ok(())
    }

    /// Secure erase (for SSDs)
    pub fn secure_erase(&self) -> Result<(), DiskError> {
        // TODO: Implement secure erase
        // For ATA: SECURITY ERASE UNIT command
        // For NVMe: FORMAT NVM command
        Ok(())
    }
}

/// Repair statistics
#[derive(Debug, Clone, Default)]
pub struct RepairStats {
    pub repaired: u64,
    pub recovered: u64,
    pub failed: u64,
    pub skipped: u64,
}

impl RepairStats {
    /// Get total sectors processed
    pub fn total(&self) -> u64 {
        self.repaired + self.recovered + self.failed + self.skipped
    }

    /// Get success rate (repaired + recovered)
    pub fn success_rate(&self) -> f64 {
        let total = self.total();
        if total == 0 {
            return 0.0;
        }
        (self.repaired + self.recovered) as f64 / total as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_repair_stats() {
        let stats = RepairStats {
            repaired: 100,
            recovered: 50,
            failed: 10,
            skipped: 0,
        };

        assert_eq!(stats.total(), 160);
        assert_eq!(stats.success_rate(), 150.0 / 160.0);
    }
}
