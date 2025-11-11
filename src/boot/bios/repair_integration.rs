// Repair engine integration for BIOS bootloader
// Connects menu selection with repair operations

#![no_std]
#![no_main]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

#[cfg(feature = "alloc")]
extern crate alloc;

use crate::boot::bios::disk_detection::BiosDiskDetector;
use crate::boot::bios::menu_integration::BiosMenuIntegration;
use crate::disk::DiskError;
use crate::ui::menu::RepairOption;
use crate::repair::{RepairConfig, ScanPattern};

// VGA text mode helper
mod vga {
    const VGA_BUFFER: *mut u16 = 0xB8000 as *mut u16;

    pub fn print_string(s: &str) {
        unsafe {
            let mut offset = 0;
            for &byte in s.as_bytes() {
                if offset >= 80 * 25 {
                    break;
                }
                core::ptr::write_volatile(
                    VGA_BUFFER.add(offset),
                    (0x07 as u16) << 8 | byte as u16,
                );
                offset += 1;
            }
        }
    }
}

/// BIOS repair integration
pub struct BiosRepairIntegration;

impl BiosRepairIntegration {
    /// Run repair workflow
    #[cfg(feature = "alloc")]
    pub fn run_repair_workflow() -> Result<(), DiskError> {
        // 1. Detect disks
        let disks = BiosDiskDetector::detect_via_ata_ports()?;

        if disks.is_empty() {
            vga::print_string("No disks found.\n");
            return Ok(());
        }

        // 2. Show disk selection menu
        let selected_disk_index = match BiosMenuIntegration::show_disk_selection()? {
            Some(index) => index,
            None => {
                vga::print_string("Cancelled.\n");
                return Ok(());
            }
        };

        if selected_disk_index >= disks.len() {
            vga::print_string("Invalid disk selection.\n");
            return Err(DiskError::InvalidParameter);
        }

        let selected_disk = &disks[selected_disk_index];

        // 3. Show repair options menu
        let repair_option = match BiosMenuIntegration::show_repair_options() {
            Some(option) => option,
            None => {
                vga::print_string("Cancelled.\n");
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
            },
            RepairOption::FullScan => RepairConfig {
                scan_pattern: ScanPattern::Random,
                max_retries: 5,
                timeout_ms: 10000,
                aggressive_correction: true,
            },
            RepairOption::SmartCheck => {
                // TODO: Implement SMART check
                vga::print_string("SMART check not yet implemented.\n");
                return Ok(());
            }
        };

        // 5. Initialize repair engine
        // TODO: Create disk interface wrapper for BIOS disk access
        // For now, just display message
        let info = format!(
            "Starting repair on disk: {} ({})\n",
            selected_disk.model,
            format_size(selected_disk.size_bytes)
        );
        vga::print_string(&info);

        // TODO: Create BIOS disk wrapper implementing Disk trait
        // TODO: Initialize RepairEngine with disk
        // TODO: Run scan_and_repair
        // TODO: Display progress
        // TODO: Display results

        vga::print_string("Repair engine integration pending.\n");

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

