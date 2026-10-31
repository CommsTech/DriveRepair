// SMART command implementation for ATA drives
// Gate 0: stubs return Unsupported / Unavailable — never Ok(true) / Ok(empty) success

use crate::disk::ata_port_io::AtaPortIO;
use crate::disk::DiskError;
use crate::smart::{SmartAttribute, SmartHealthStatus, SmartTestType};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// SMART command executor for ATA drives
pub struct AtaSmartExecutor {
    port_io: AtaPortIO,
}

impl AtaSmartExecutor {
    /// Create new SMART executor
    pub fn new(primary: bool) -> Self {
        Self {
            port_io: AtaPortIO::new(primary),
        }
    }

    /// Enable SMART
    pub fn enable(&self) -> Result<(), DiskError> {
        let _ = &self.port_io;
        // EXPERIMENTAL/UNSUPPORTED: SMART ENABLE OPERATIONS not implemented
        Err(DiskError::Unsupported)
    }

    /// Disable SMART
    pub fn disable(&self) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SMART DISABLE OPERATIONS not implemented
        Err(DiskError::Unsupported)
    }

    /// Check if SMART is enabled
    pub fn is_enabled(&self) -> Result<bool, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SMART status query not implemented
        Err(DiskError::Unavailable)
    }

    /// Read SMART attributes
    #[cfg(feature = "alloc")]
    pub fn read_attributes(&self) -> Result<Vec<SmartAttribute>, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SMART READ DATA not implemented
        // Do not return Ok(empty) — that would be interpreted as Healthy after Gate 0 fix,
        // but empty success is still dishonest; fail closed.
        Err(DiskError::Unsupported)
    }

    /// Read specific SMART attribute
    pub fn read_attribute(&self, _id: u8) -> Result<SmartAttribute, DiskError> {
        #[cfg(feature = "alloc")]
        {
            let _ = self.read_attributes()?;
        }
        Err(DiskError::Unsupported)
    }

    /// Get SMART health status — must not call interpret_health on empty success
    #[cfg(feature = "alloc")]
    pub fn health_status(&self) -> Result<SmartHealthStatus, DiskError> {
        match self.read_attributes() {
            Ok(attributes) if attributes.is_empty() => Ok(SmartHealthStatus::Unknown),
            Ok(attributes) => Ok(crate::smart::SmartParser::interpret_health(&attributes)),
            Err(DiskError::Unsupported) => Ok(SmartHealthStatus::Unknown),
            Err(DiskError::Unavailable) => Ok(SmartHealthStatus::UnableToQuery),
            Err(e) => Err(e),
        }
    }

    /// Run SMART self-test
    pub fn run_self_test(&self, _test_type: SmartTestType) -> Result<(), DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SMART EXECUTE OFFLINE IMMEDIATE not implemented
        Err(DiskError::Unsupported)
    }

    /// Read SMART threshold values
    #[cfg(feature = "alloc")]
    pub fn read_thresholds(&self) -> Result<Vec<u8>, DiskError> {
        // EXPERIMENTAL/UNSUPPORTED: SMART READ THRESHOLDS not implemented
        Err(DiskError::Unsupported)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ata_smart_executor_creation() {
        let _executor = AtaSmartExecutor::new(true);
    }

    #[test]
    fn stubs_fail_closed() {
        let executor = AtaSmartExecutor::new(true);
        assert_eq!(executor.enable(), Err(DiskError::Unsupported));
        assert_eq!(executor.is_enabled(), Err(DiskError::Unavailable));
        #[cfg(feature = "alloc")]
        {
            assert_eq!(executor.read_attributes().unwrap_err(), DiskError::Unsupported);
            assert_eq!(
                executor.health_status().unwrap(),
                SmartHealthStatus::Unknown
            );
        }
    }
}
