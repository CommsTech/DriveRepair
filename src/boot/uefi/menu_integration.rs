// Integration of menu system with UEFI bootloader
// Provides interactive disk selection and repair options


use uefi::prelude::*;
use uefi::table::boot::BootServices;
use uefi::table::SystemTable;
use uefi::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

use crate::disk_enumeration::UefiDiskEnumerator;
use drive_repair::disk::DiskInfo;
use drive_repair::ui::menu::{Menu, RepairOption};

/// UEFI menu integration
pub struct UefiMenuIntegration<'a> {
    boot_services: &'a BootServices,
    system_table: &'a SystemTable<Boot>,
}

impl<'a> UefiMenuIntegration<'a> {
    /// Create new UEFI menu integration
    pub fn new(boot_services: &'a BootServices, system_table: &'a SystemTable<Boot>) -> Self {
        Self {
            boot_services,
            system_table,
        }
    }

    /// Show disk selection menu and return selected disk index
    #[cfg(feature = "alloc")]
    pub fn show_disk_selection(&self) -> Result<Option<usize>, Status> {
        // Enumerate disks
        let enumerator = UefiDiskEnumerator::new(self.boot_services);
        let disks = enumerator.enumerate_disks()?;

        if disks.is_empty() {
            self.system_table
                .stdout()
                .output_string("No disks found.\n")?;
            return Ok(None);
        }

        // Display disk list
        self.system_table
            .stdout()
            .output_string("\n=== Available Disks ===\n")?;

        for (index, disk) in disks.iter().enumerate() {
            let interface_str = match disk.interface {
                crate::disk::DiskInterface::ATA => "ATA",
                crate::disk::DiskInterface::SATA => "SATA",
                crate::disk::DiskInterface::NVMe => "NVMe",
                crate::disk::DiskInterface::USB => "USB",
                crate::disk::DiskInterface::Unknown => "Unknown",
            };

            let size_str = format_size(disk.size_bytes);
            let info = format!(
                "[{}] {} - {} ({})\n",
                index, interface_str, disk.model, size_str
            );
            self.system_table.stdout().output_string(&info)?;
        }

        // EXPERIMENTAL/UNSUPPORTED: Simple Text Input selection not wired.
        // Gate 0: require explicit selection — never auto-select disk 0.
        Ok(None)
    }

    /// Show repair options menu and return selected option
    pub fn show_repair_options(&self) -> Result<Option<RepairOption>, Status> {
        // Display repair options
        self.system_table
            .stdout()
            .output_string("\n=== Repair Options ===\n")?;
        self.system_table
            .stdout()
            .output_string("[0] Quick Scan - Fast surface scan\n")?;
        self.system_table
            .stdout()
            .output_string("[1] Full Scan - Complete surface scan\n")?;
        self.system_table
            .stdout()
            .output_string("[2] SMART Check - Check SMART status only\n")?;
        self.system_table
            .stdout()
            .output_string("[3] Cancel - Return to main menu\n")?;

        // EXPERIMENTAL/UNSUPPORTED: Simple Text Input selection not wired.
        // Gate 0: require explicit selection — never default to QuickScan.
        Ok(None)
    }
}

/// Format size in human-readable format
#[cfg(feature = "alloc")]
fn format_size(bytes: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut size = bytes as f64;
    let mut unit_index = 0;

    while size >= 1024.0 && unit_index < UNITS.len() - 1 {
        size /= 1024.0;
        unit_index += 1;
    }

    format!("{:.2} {}", size, UNITS[unit_index])
}
