// Repair engine integration for UEFI bootloader
// Connects menu selection with repair operations

#![no_std]
#![no_main]

use uefi::prelude::*;
use uefi::table::boot::BootServices;
use uefi::table::SystemTable;
use uefi::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

use crate::boot::uefi::disk_enumeration::UefiDiskEnumerator;
use crate::boot::uefi::disk_wrapper::UefiDisk;
use crate::boot::uefi::menu_integration::UefiMenuIntegration;
use crate::ui::menu::RepairOption;
use crate::repair::{RepairEngine, RepairConfig, ScanPattern};

/// UEFI repair integration
pub struct UefiRepairIntegration<'a> {
    boot_services: &'a BootServices,
    system_table: &'a SystemTable<Boot>,
}

impl<'a> UefiRepairIntegration<'a> {
    /// Create new UEFI repair integration
    pub fn new(boot_services: &'a BootServices, system_table: &'a SystemTable<Boot>) -> Self {
        Self {
            boot_services,
            system_table,
        }
    }

    /// Run repair workflow
    #[cfg(feature = "alloc")]
    pub fn run_repair_workflow(&self) -> Result<(), Status> {
        // 1. Enumerate disks
        let enumerator = UefiDiskEnumerator::new(self.boot_services);
        let disks = match enumerator.enumerate_disks() {
            Ok(disks) => disks,
            Err(e) => {
                self.system_table
                    .stdout()
                    .output_string(&format!("ERROR: Failed to enumerate disks: {:?}\n", e))?;
                return Err(e);
            }
        };

        if disks.is_empty() {
            self.system_table
                .stdout()
                .output_string("No disks found.\n")?;
            return Ok(());
        }

        // 2. Show disk selection menu
        let menu = UefiMenuIntegration::new(self.boot_services, self.system_table);
        let selected_disk_index = match menu.show_disk_selection()? {
            Some(index) => index,
            None => {
                self.system_table.stdout().output_string("Cancelled.\n")?;
                return Ok(());
            }
        };

        if selected_disk_index >= disks.len() {
            self.system_table
                .stdout()
                .output_string("Invalid disk selection.\n")?;
            return Err(Status::INVALID_PARAMETER);
        }

        let selected_disk = &disks[selected_disk_index];

        // 3. Show repair options menu
        let repair_option = match menu.show_repair_options()? {
            Some(option) => option,
            None => {
                self.system_table.stdout().output_string("Cancelled.\n")?;
                return Ok(());
            }
        };

        // 4. Configure repair engine based on option
        let config = match repair_option {
            RepairOption::QuickScan => RepairConfig {
                scan_pattern: ScanPattern::Sequential,
                max_retries: 3,
                timeout_ms: 5000,
                aggressive_correction: false,
                start_sector: 0,
                end_sector: selected_disk.total_sectors,
            },
            RepairOption::FullScan => RepairConfig {
                scan_pattern: ScanPattern::Random,
                max_retries: 5,
                timeout_ms: 10000,
                aggressive_correction: true,
                start_sector: 0,
                end_sector: selected_disk.total_sectors,
            },
            RepairOption::SmartCheck => {
                // TODO: Implement SMART check
                self.system_table
                    .stdout()
                    .output_string("SMART check not yet implemented.\n")?;
                return Ok(());
            }
        };

        // 5. Initialize repair engine
        // Get handle for selected disk
        let enumerator = UefiDiskEnumerator::new(self.boot_services);
        let handles = self
            .boot_services
            .locate_handle_buffer(uefi::table::boot::SearchType::ByProtocol(
                &uefi::proto::block::BlockIO::GUID,
            ))
            .map_err(|_| Status::UNSUPPORTED)?;

        if selected_disk_index >= handles.len() {
            self.system_table
                .stdout()
                .output_string("Invalid disk handle.\n")?;
            return Err(Status::INVALID_PARAMETER);
        }

        let handle = handles[selected_disk_index];

        // Create UEFI disk wrapper
        let mut disk = UefiDisk::new(self.boot_services, handle, selected_disk.clone())
            .map_err(|_| Status::UNSUPPORTED)?;

        // Initialize repair engine
        let mut repair_engine = RepairEngine::new(disk, config);

        self.system_table.stdout().output_string(&format!(
            "Starting repair on disk: {} ({})\n",
            selected_disk.model,
            format_size(selected_disk.size_bytes)
        ))?;

        // Run scan and repair with progress callback
        let progress_callback = |current: u64, total: u64, result: crate::repair::RepairResult| {
            // TODO: Display progress via UEFI output
            // For now, this is a placeholder
            let _ = (current, total, result);
        };

        match repair_engine.scan_and_repair(progress_callback) {
            Ok(stats) => {
                self.system_table.stdout().output_string(&format!(
                    "Repair completed. Sectors repaired: {}, recovered: {}, failed: {}\n",
                    stats.sectors_repaired, stats.sectors_recovered, stats.sectors_failed
                ))?;
            }
            Err(e) => {
                self.system_table
                    .stdout()
                    .output_string(&format!("Repair failed: {:?}\n", e))?;
                return Err(Status::ABORTED);
            }
        }

        Ok(())
    }
}

/// Format size in human-readable format
#[cfg(feature = "alloc")]
fn format_size(bytes: u64) -> alloc::string::String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut size = bytes as f64;
    let mut unit_index = 0;

    while size >= 1024.0 && unit_index < UNITS.len() - 1 {
        size /= 1024.0;
        unit_index += 1;
    }

    // Simple formatting without format! macro
    let mut result = alloc::string::String::new();
    result.push_str(&alloc::string::ToString::to_string(&size));
    result.push_str(" ");
    result.push_str(UNITS[unit_index]);
    result
}

