// SMART (Self-Monitoring, Analysis, and Reporting Technology) interface
// Provides health monitoring and predictive failure analysis

#![allow(dead_code)]

use crate::disk::DiskError;
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// SMART attribute ID constants
pub const SMART_ATTR_POWER_ON_HOURS: u8 = 0x09;
pub const SMART_ATTR_POWER_CYCLE_COUNT: u8 = 0x0C;
pub const SMART_ATTR_REALLOCATED_SECTORS: u8 = 0x05;
pub const SMART_ATTR_CURRENT_PENDING_SECTORS: u8 = 0xC5;
pub const SMART_ATTR_OFFLINE_UNCORRECTABLE: u8 = 0xC6;
pub const SMART_ATTR_CRC_ERROR_COUNT: u8 = 0xC7;
pub const SMART_ATTR_WEAR_LEVELING_COUNT: u8 = 0xE7;
pub const SMART_ATTR_MEDIA_WEAROUT_INDICATOR: u8 = 0xE8;
pub const SMART_ATTR_HOST_WRITES: u8 = 0xF1;
pub const SMART_ATTR_HOST_READS: u8 = 0xF2;

/// SMART attribute structure
#[derive(Debug, Clone, Copy)]
pub struct SmartAttribute {
    pub id: u8,
    pub flags: u16,
    pub current: u8,
    pub worst: u8,
    pub raw_value: u64,
    pub threshold: u8,
}

/// SMART health status
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SmartHealthStatus {
    /// Drive is healthy
    Healthy,
    /// Drive has warnings
    Warning,
    /// Drive is failing
    Failing,
    /// Status unknown
    Unknown,
}

/// SMART interface trait
pub trait SmartInterface {
    /// Read SMART attributes
    #[cfg(feature = "alloc")]
    fn read_attributes(&self) -> Result<Vec<SmartAttribute>, DiskError>;

    /// Read specific SMART attribute
    fn read_attribute(&self, id: u8) -> Result<SmartAttribute, DiskError>;

    /// Get SMART health status
    fn health_status(&self) -> Result<SmartHealthStatus, DiskError>;

    /// Enable SMART
    fn enable(&self) -> Result<(), DiskError>;

    /// Disable SMART
    fn disable(&self) -> Result<(), DiskError>;

    /// Check if SMART is enabled
    fn is_enabled(&self) -> Result<bool, DiskError>;

    /// Run SMART self-test
    fn run_self_test(&self, test_type: SmartTestType) -> Result<(), DiskError>;
}

/// SMART self-test types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SmartTestType {
    /// Short self-test
    Short,
    /// Extended self-test
    Extended,
    /// Conveyance self-test
    Conveyance,
}

/// SMART attribute parser
pub struct SmartParser;

impl SmartParser {
    /// Parse SMART attribute from raw data
    pub fn parse_attribute(data: &[u8]) -> Option<SmartAttribute> {
        if data.len() < 12 {
            return None;
        }

        Some(SmartAttribute {
            id: data[0],
            flags: u16::from_le_bytes([data[1], data[2]]),
            current: data[3],
            worst: data[4],
            raw_value: u64::from_le_bytes([
                data[5], data[6], data[7], data[8], data[9], data[10], data[11], 0,
            ]),
            threshold: data[12],
        })
    }

    /// Interpret SMART health status from attributes
    pub fn interpret_health(attributes: &[SmartAttribute]) -> SmartHealthStatus {
        let mut has_warnings = false;
        let mut has_failures = false;

        for attr in attributes {
            // Check if attribute is below threshold
            if attr.current < attr.threshold && attr.threshold > 0 {
                has_failures = true;
            }

            // Check critical attributes
            match attr.id {
                SMART_ATTR_REALLOCATED_SECTORS => {
                    if attr.raw_value > 0 {
                        has_warnings = true;
                    }
                }
                SMART_ATTR_CURRENT_PENDING_SECTORS => {
                    if attr.raw_value > 0 {
                        has_warnings = true;
                    }
                }
                SMART_ATTR_OFFLINE_UNCORRECTABLE => {
                    if attr.raw_value > 0 {
                        has_warnings = true;
                    }
                }
                _ => {}
            }
        }

        if has_failures {
            SmartHealthStatus::Failing
        } else if has_warnings {
            SmartHealthStatus::Warning
        } else {
            SmartHealthStatus::Healthy
        }
    }

    /// Get wear leveling percentage for SSDs
    pub fn get_wear_leveling(attributes: &[SmartAttribute]) -> Option<u8> {
        for attr in attributes {
            if attr.id == SMART_ATTR_MEDIA_WEAROUT_INDICATOR {
                return Some(attr.current);
            }
        }
        None
    }

    /// Get power-on hours
    pub fn get_power_on_hours(attributes: &[SmartAttribute]) -> Option<u64> {
        for attr in attributes {
            if attr.id == SMART_ATTR_POWER_ON_HOURS {
                return Some(attr.raw_value);
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_attribute() {
        let data = [
            0x09, // ID
            0x00, 0x00, // Flags
            0x64, // Current
            0x64, // Worst
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // Raw value
            0x00, // Threshold
        ];

        if let Some(attr) = SmartParser::parse_attribute(&data) {
            assert_eq!(attr.id, 0x09);
            assert_eq!(attr.current, 0x64);
        } else {
            panic!("Failed to parse attribute");
        }
    }
}
