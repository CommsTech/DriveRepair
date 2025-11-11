// Disk detection and enumeration
// Discovers all connected drives via PCI, AHCI, and USB

use crate::disk::ata::AtaDisk;
use crate::disk::nvme::{NvmeController, NvmeDisk};
use crate::disk::sata::{AhciController, SataDisk};
use crate::disk::usb::UsbDisk;
use crate::disk::{Disk, DiskError, DiskInfo};

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::boxed::Box;
#[cfg(feature = "alloc")]
use alloc::string::String;
#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// Disk enumerator
pub struct DiskEnumerator;

impl DiskEnumerator {
    /// Enumerate all available disks
    #[cfg(feature = "alloc")]
    pub fn enumerate() -> Result<Vec<Box<dyn Disk>>, DiskError> {
        let mut disks: Vec<Box<dyn Disk>> = Vec::new();

        // Enumerate NVMe drives
        if let Ok(controller) = NvmeController::detect() {
            let namespace_count = controller.namespace_count();
            for namespace_id in 1..=namespace_count {
                // Clone controller for each namespace (or use references)
                // For now, create a new controller for each namespace
                // TODO: Refactor to use references or Arc
                if let Ok(disk) = NvmeDisk::new(NvmeController::detect().unwrap(), namespace_id) {
                    disks.push(Box::new(disk));
                }
            }
        }

        // Enumerate SATA drives via AHCI
        if let Ok(controller) = AhciController::detect() {
            let port_count = controller.port_count();
            for port in 0..port_count {
                // Clone controller for each port (or use references)
                // For now, create a new controller for each port
                // TODO: Refactor to use references or Arc
                if let Ok(disk) = SataDisk::new(AhciController::detect().unwrap(), port) {
                    disks.push(Box::new(disk));
                }
            }
        }

        // Enumerate ATA/IDE drives
        // Primary channel, master
        if let Ok(disk) = AtaDisk::new(true, true) {
            if disk.is_ready() {
                disks.push(Box::new(disk));
            }
        }
        // Primary channel, slave
        if let Ok(disk) = AtaDisk::new(true, false) {
            if disk.is_ready() {
                disks.push(Box::new(disk));
            }
        }
        // Secondary channel, master
        if let Ok(disk) = AtaDisk::new(false, true) {
            if disk.is_ready() {
                disks.push(Box::new(disk));
            }
        }
        // Secondary channel, slave
        if let Ok(disk) = AtaDisk::new(false, false) {
            if disk.is_ready() {
                disks.push(Box::new(disk));
            }
        }

        // Enumerate USB drives
        // TODO: Implement USB enumeration
        // For now, try common device addresses
        for addr in 1..=16 {
            if let Ok(disk) = UsbDisk::new(addr) {
                if disk.is_ready() {
                    disks.push(Box::new(disk));
                }
            }
        }

        Ok(disks)
    }

    /// Get disk information list
    #[cfg(feature = "alloc")]
    pub fn get_disk_list() -> Result<Vec<DiskInfo>, DiskError> {
        let disks = Self::enumerate()?;
        let mut info_list = Vec::new();

        for disk in disks {
            if let Ok(info) = disk.info() {
                info_list.push(info);
            }
        }

        Ok(info_list)
    }
}

/// Helper function to format disk size
#[cfg(feature = "alloc")]
pub fn format_size(bytes: u64) -> alloc::string::String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB", "PB"];
    let mut size = bytes as f64;
    let mut unit_idx = 0;

    while size >= 1024.0 && unit_idx < UNITS.len() - 1 {
        size /= 1024.0;
        unit_idx += 1;
    }

    {
        // Simple formatting without format! macro
        let int_part = size as u64;
        let frac_part = ((size - int_part as f64) * 100.0) as u32;
        let mut s = String::new();
        // Convert int_part to string manually
        let mut n = int_part;
        if n == 0 {
            s.push('0');
        } else {
            let mut digits = Vec::new();
            while n > 0 {
                digits.push((b'0' + (n % 10) as u8) as char);
                n /= 10;
            }
            for &digit in digits.iter().rev() {
                s.push(digit);
            }
        }
        s.push('.');
        if frac_part < 10 {
            s.push('0');
        }
        // Convert frac_part to string manually
        let mut n = frac_part;
        if n == 0 {
            s.push('0');
        } else {
            let mut digits = Vec::new();
            while n > 0 {
                digits.push((b'0' + (n % 10) as u8) as char);
                n /= 10;
            }
            for &digit in digits.iter().rev() {
                s.push(digit);
            }
        }
        s.push(' ');
        s.push_str(UNITS[unit_idx]);
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_size() {
        assert_eq!(format_size(512), "512.00 B");
        assert_eq!(format_size(1024), "1.00 KB");
        assert_eq!(format_size(1024 * 1024), "1.00 MB");
        assert_eq!(format_size(1024 * 1024 * 1024), "1.00 GB");
        assert_eq!(format_size(1024u64.pow(4)), "1.00 TB");
    }
}
