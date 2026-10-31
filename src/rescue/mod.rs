// Rescue / ddrescue orchestration scaffolding (Gate 0)
// Command builder + identity validation only — NO real-disk execution

#![cfg(feature = "alloc")]

use crate::disk::{DeviceIdentity, DiskError};
use alloc::string::String;
use alloc::vec::Vec;
use core::result::Result;

/// Re-export identity type for rescue callers
pub use crate::disk::DeviceIdentity as RescueDeviceIdentity;

/// Validate that source and destination are distinct devices.
/// Rejects matching paths or matching non-empty serials.
pub fn validate_source_destination(
    source: &DeviceIdentity,
    destination: &DeviceIdentity,
) -> Result<(), DiskError> {
    if source.is_unknown() || destination.is_unknown() {
        return Err(DiskError::IdentityUnknown);
    }
    if source.conflicts_with(destination) {
        return Err(DiskError::SourceDestinationConflict);
    }
    Ok(())
}

/// Rescue plan describing a ddrescue-style copy (not executed against real disks)
#[derive(Debug, Clone)]
pub struct RescuePlan {
    pub source: DeviceIdentity,
    pub destination: DeviceIdentity,
    pub mapfile_path: String,
    /// Source must remain read-only during rescue
    pub read_only_source: bool,
}

impl RescuePlan {
    pub fn new(
        source: DeviceIdentity,
        destination: DeviceIdentity,
        mapfile_path: impl Into<String>,
    ) -> Result<Self, DiskError> {
        validate_source_destination(&source, &destination)?;
        Ok(Self {
            source,
            destination,
            mapfile_path: mapfile_path.into(),
            read_only_source: true,
        })
    }

    /// Build a ddrescue command line (argv) without executing it.
    /// Gate 0: never invoke this against real disks from library code.
    pub fn build_ddrescue_command(&self) -> Result<Vec<String>, DiskError> {
        if !self.read_only_source {
            return Err(DiskError::WriteDenied);
        }
        validate_source_destination(&self.source, &self.destination)?;

        let mut argv = Vec::new();
        argv.push(String::from("ddrescue"));
        argv.push(String::from("-f"));
        argv.push(String::from("-n"));
        argv.push(self.source.path.clone());
        argv.push(self.destination.path.clone());
        argv.push(self.mapfile_path.clone());
        Ok(argv)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_same_path() {
        let a = DeviceIdentity::new("/dev/sda", "SER1", "M");
        let b = DeviceIdentity::new("/dev/sda", "SER2", "M");
        assert_eq!(
            validate_source_destination(&a, &b),
            Err(DiskError::SourceDestinationConflict)
        );
    }

    #[test]
    fn rejects_same_serial() {
        let a = DeviceIdentity::new("/dev/sda", "SERIALX", "M");
        let b = DeviceIdentity::new("/dev/sdb", "SERIALX", "M");
        assert_eq!(
            validate_source_destination(&a, &b),
            Err(DiskError::SourceDestinationConflict)
        );
    }

    #[test]
    fn rejects_unknown_identity() {
        let a = DeviceIdentity::new("", "", "");
        let b = DeviceIdentity::new("/dev/sdb", "SER2", "M");
        assert_eq!(
            validate_source_destination(&a, &b),
            Err(DiskError::IdentityUnknown)
        );
    }

    #[test]
    fn accepts_distinct_and_builds_command() {
        let a = DeviceIdentity::new("/dev/sda", "SER1", "M");
        let b = DeviceIdentity::new("/dev/sdb", "SER2", "M");
        let plan = RescuePlan::new(a, b, "/tmp/mapfile").expect("plan");
        let argv = plan.build_ddrescue_command().expect("argv");
        assert_eq!(argv[0], "ddrescue");
        assert!(argv.contains(&String::from("/dev/sda")));
        assert!(argv.contains(&String::from("/dev/sdb")));
        assert!(argv.contains(&String::from("/tmp/mapfile")));
    }
}
