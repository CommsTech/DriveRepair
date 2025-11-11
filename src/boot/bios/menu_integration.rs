// Integration of menu system with BIOS bootloader
// Provides interactive disk selection and repair options

#![no_std]
#![no_main]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

use crate::boot::bios::disk_detection::BiosDiskDetector;
use crate::disk::DiskInfo;
use crate::ui::menu::RepairOption;
// VGA text mode helper - defined inline for now
mod vga {
    /// VGA text buffer address (0xB8000)
    const VGA_BUFFER: *mut u16 = 0xB8000 as *mut u16;
    
    /// Print string to VGA buffer
    pub fn print_string(s: &str) {
        unsafe {
            let mut offset = 0;
            for &byte in s.as_bytes() {
                if offset >= 80 * 25 {
                    break;
                }
                core::ptr::write_volatile(
                    VGA_BUFFER.add(offset),
                    (0x07 as u16) << 8 | byte as u16, // Light gray on black
                );
                offset += 1;
            }
        }
    }
}

/// BIOS menu integration
pub struct BiosMenuIntegration;

impl BiosMenuIntegration {
    /// Show disk selection menu and return selected disk index
    #[cfg(feature = "alloc")]
    pub fn show_disk_selection() -> Result<Option<usize>, crate::disk::DiskError> {
        // Detect disks
        // Try INT 13h first, then fall back to ATA port I/O
        let disks = match BiosDiskDetector::detect_via_int13h() {
            Ok(d) if !d.is_empty() => d,
            _ => BiosDiskDetector::detect_via_ata_ports()?,
        };

        if disks.is_empty() {
            VgaTextMode::print_string("No disks found.\n");
            return Ok(None);
        }

        // Display disk list
        VgaTextMode::print_string("\n=== Available Disks ===\n");

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
            VgaTextMode::print_string(&info);
        }

        // TODO: Implement keyboard input for selection
        // Use BIOS INT 16h for keyboard input
        // For now, return first disk
        Ok(Some(0))
    }

    /// Show repair options menu and return selected option
    pub fn show_repair_options() -> Option<RepairOption> {
        // Display repair options
        VgaTextMode::print_string("\n=== Repair Options ===\n");
        VgaTextMode::print_string("[0] Quick Scan - Fast surface scan\n");
        VgaTextMode::print_string("[1] Full Scan - Complete surface scan\n");
        VgaTextMode::print_string("[2] SMART Check - Check SMART status only\n");
        VgaTextMode::print_string("[3] Cancel - Return to main menu\n");

        // TODO: Implement keyboard input for selection
        // Use BIOS INT 16h for keyboard input
        // For now, return Quick Scan
        Some(RepairOption::QuickScan)
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

