// User interface for bootable environment
// Text-based UI for drive selection, progress, and status reporting

#![allow(dead_code)]

use crate::disk::{Disk, DiskInfo, DiskInterface};
use crate::repair::{RepairConfig, RepairResult, RepairStats};
use crate::smart::{SmartHealthStatus, SmartInterface};

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;
#[cfg(feature = "alloc")]
use alloc::vec::Vec;

#[cfg(feature = "std")]
extern crate std;

/// UI color codes (for terminals that support ANSI)
pub mod colors {
    pub const RESET: &str = "\x1b[0m";
    pub const RED: &str = "\x1b[31m";
    pub const GREEN: &str = "\x1b[32m";
    pub const YELLOW: &str = "\x1b[33m";
    pub const BLUE: &str = "\x1b[34m";
    pub const CYAN: &str = "\x1b[36m";
    pub const WHITE: &str = "\x1b[37m";
}

/// User interface manager
pub struct UserInterface;

impl UserInterface {
    /// Display welcome screen
    #[cfg(feature = "std")]
    pub fn show_welcome() {
        Self::clear_screen();
        println!("{}", "=".repeat(60));
        println!("  DriveRepair by commstech v0.0.1");
        println!("  Drive Repair Tool - Modern Edition");
        println!("  Supports drives from 64GB to 20TB");
        println!("  ATA, SATA, NVMe, and USB support");
        println!("  x86_64 and ARM64 architectures");
        println!("{}", "=".repeat(60));
        println!();
    }

    #[cfg(not(feature = "std"))]
    pub fn show_welcome() {
        // No-op for no_std environment
    }

    /// Display disk list
    #[cfg(all(feature = "alloc", feature = "std"))]
    pub fn show_disk_list(disks: &[DiskInfo]) {
        println!("Detected Drives:");
        println!("{}", "-".repeat(60));
        println!(
            "{:<4} {:<8} {:<20} {:<12} {:<10}",
            "ID", "Type", "Model", "Size", "Status"
        );
        println!("{}", "-".repeat(60));

        for (index, disk) in disks.iter().enumerate() {
            let interface_str = match disk.interface {
                DiskInterface::ATA => "ATA",
                DiskInterface::SATA => "SATA",
                DiskInterface::NVMe => "NVMe",
                DiskInterface::USB => "USB",
            };

            let size_str = Self::format_size(disk.size_bytes);
            let status = "Ready"; // TODO: Get actual status

            println!(
                "{:<4} {:<8} {:<20} {:<12} {:<10}",
                index,
                interface_str,
                Self::truncate_string(&disk.model, 20),
                size_str,
                status
            );
        }
        println!();
    }

    /// Prompt for disk selection
    #[cfg(feature = "std")]
    pub fn prompt_disk_selection(max_index: usize) -> Option<usize> {
        print!("Select drive to repair (0-{}): ", max_index);
        // TODO: Implement input reading
        // For now, return None
        None
    }

    /// Display disk information
    #[cfg(feature = "std")]
    pub fn show_disk_info(disk: &DiskInfo) {
        println!("Drive Information:");
        println!("{}", "-".repeat(60));
        println!("Interface: {:?}", disk.interface);
        println!("Model: {}", disk.model);
        println!("Serial: {}", disk.serial);
        println!("Firmware: {}", disk.firmware);
        println!("Size: {}", Self::format_size(disk.size_bytes));
        println!("Sector Size: {} bytes", disk.sector_size);
        println!("Total Sectors: {}", disk.total_sectors);
        println!();
    }

    /// Display SMART health status
    #[cfg(feature = "std")]
    pub fn show_smart_status(status: SmartHealthStatus) {
        print!("SMART Status: ");
        match status {
            SmartHealthStatus::Healthy => {
                println!("{}Healthy{}", colors::GREEN, colors::RESET);
            }
            SmartHealthStatus::Warning => {
                println!("{}Warning{}", colors::YELLOW, colors::RESET);
            }
            SmartHealthStatus::Failing => {
                println!("{}Failing{}", colors::RED, colors::RESET);
            }
            SmartHealthStatus::Unknown => {
                println!("Unknown");
            }
        }
    }

    /// Display repair progress
    #[cfg(feature = "std")]
    pub fn show_repair_progress(current: u64, total: u64, result: RepairResult) {
        let percentage = if total > 0 {
            (current as f64 / total as f64 * 100.0) as u32
        } else {
            0
        };

        let bar_width = 50;
        let filled = (bar_width as f64 * percentage as f64 / 100.0) as usize;
        let bar = "=".repeat(filled) + &" ".repeat(bar_width - filled);

        let status = match result {
            RepairResult::Repaired => {
                let mut s = String::from(colors::GREEN);
                s.push_str("Repaired");
                s.push_str(colors::RESET);
                s
            }
            RepairResult::Recovered => {
                let mut s = String::from(colors::YELLOW);
                s.push_str("Recovered");
                s.push_str(colors::RESET);
                s
            }
            RepairResult::Failed => {
                let mut s = String::from(colors::RED);
                s.push_str("Failed");
                s.push_str(colors::RESET);
                s
            }
            RepairResult::Skipped => String::from("Skipped"),
        };

        print!(
            "\r[{}] {}% - Sector {} - {}    ",
            bar, percentage, current, status
        );
    }

    /// Display repair statistics
    #[cfg(feature = "std")]
    pub fn show_repair_stats(stats: &RepairStats) {
        println!();
        println!("Repair Statistics:");
        println!("{}", "-".repeat(60));
        println!("Repaired:  {}", stats.repaired);
        println!("Recovered: {}", stats.recovered);
        println!("Failed:    {}", stats.failed);
        println!("Skipped:   {}", stats.skipped);
        println!("Total:     {}", stats.total());
        println!("Success Rate: {:.2}%", stats.success_rate() * 100.0);
        println!();
    }

    /// Display repair configuration
    #[cfg(feature = "std")]
    pub fn show_repair_config(config: &RepairConfig) {
        println!("Repair Configuration:");
        println!("{}", "-".repeat(60));
        println!("Max Retries: {}", config.max_retries);
        println!("Timeout: {} ms", config.timeout_ms);
        println!("Scan Pattern: {:?}", config.scan_pattern);
        println!("Aggressive Correction: {}", config.aggressive_correction);
        println!("Enable TRIM: {}", config.enable_trim);
        println!("Start Sector: {}", config.start_sector);
        println!("End Sector: {}", config.end_sector);
        println!();
    }

    /// Clear screen
    #[cfg(feature = "std")]
    pub fn clear_screen() {
        // ANSI escape sequence to clear screen
        print!("\x1b[2J\x1b[H");
    }

    #[cfg(not(feature = "std"))]
    pub fn clear_screen() {
        // No-op for no_std environment
    }

    /// Format size for display
    #[cfg(feature = "alloc")]
    fn format_size(bytes: u64) -> String {
        const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB", "PB"];
        let mut size = bytes as f64;
        let mut unit_idx = 0;

        while size >= 1024.0 && unit_idx < UNITS.len() - 1 {
            size /= 1024.0;
            unit_idx += 1;
        }

        {
            // Simple formatting without format! macro
            // For no_std, we'll use a simpler approach
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

    /// Truncate string to specified length
    #[cfg(feature = "alloc")]
    fn truncate_string(s: &str, max_len: usize) -> String {
        if s.len() <= max_len {
            String::from(s)
        } else {
            {
                let mut result = String::from(&s[..max_len - 3]);
                result.push_str("...");
                result
            }
        }
    }
}
