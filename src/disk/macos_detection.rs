// macOS-specific disk detection using system commands
// Uses diskutil and system_profiler to enumerate drives

#![cfg(target_os = "macos")]

use crate::disk::{DiskError, DiskInfo, DiskInterface};
use alloc::string::String;
use alloc::vec::Vec;
use std::process::Command;

/// macOS disk enumerator using system commands
pub struct MacOSDiskEnumerator;

impl MacOSDiskEnumerator {
    /// Get disk identifier from diskutil list output
    fn get_disk_identifier(disk_id: &str) -> Option<String> {
        // Extract disk identifier (e.g., "disk0" from "/dev/disk0")
        if disk_id.starts_with("/dev/") {
            Some(disk_id.strip_prefix("/dev/").unwrap().to_string())
        } else {
            Some(disk_id.to_string())
        }
    }

    /// Enumerate disks using diskutil
    pub fn enumerate_via_diskutil() -> Result<Vec<DiskInfo>, DiskError> {
        let mut disks = Vec::new();

        // Get disk list using diskutil
        let output = Command::new("diskutil")
            .arg("list")
            .arg("-plist")
            .output()
            .map_err(|_| DiskError::HardwareError)?;

        if !output.status.success() {
            return Err(DiskError::HardwareError);
        }

        // Parse diskutil output (simplified - for full implementation, parse plist)
        // For now, use a simpler approach with diskutil list
        let list_output = Command::new("diskutil")
            .arg("list")
            .output()
            .map_err(|_| DiskError::HardwareError)?;

        if !list_output.status.success() {
            return Err(DiskError::HardwareError);
        }

        let output_str = String::from_utf8_lossy(&list_output.stdout);
        let lines: Vec<&str> = output_str.lines().collect();

        // Parse diskutil output
        let mut current_disk: Option<String> = None;
        let mut disk_size: Option<u64> = None;
        let mut disk_identifiers: Vec<(String, u64)> = Vec::new();

        for line in lines {
            let line = line.trim();
            
            // Look for physical disk entries (e.g., "/dev/disk0 (internal, physical):")
            if line.starts_with("/dev/disk") && (line.contains("physical") || line.contains("internal")) {
                // Extract disk identifier (e.g., "/dev/disk0")
                if let Some(disk_id) = line.split_whitespace().next() {
                    if disk_id.starts_with("/dev/disk") {
                        current_disk = Some(disk_id.to_string());
                    }
                }
            }
            
            // Look for size information (e.g., "*1.0 TB")
            if current_disk.is_some()
                && line.contains("*")
                && (line.contains("GB") || line.contains("TB") || line.contains("MB"))
            {
                disk_size = Self::parse_size(line);
            }

            // When we have both disk and size, store for later processing
            if let (Some(ref disk_id), Some(size)) = (&current_disk, &disk_size) {
                if *size > 0 {
                    if let Some(identifier) = Self::get_disk_identifier(disk_id) {
                        disk_identifiers.push((identifier, *size));
                    }
                    current_disk = None;
                    disk_size = None;
                }
            }
        }

        // Process stored disk identifiers
        for (identifier, size) in disk_identifiers {
            if let Ok(mut info) = Self::get_disk_info(&format!("/dev/{}", identifier)) {
                // Update size if we parsed it from the list
                if info.size_bytes == 0 {
                    info.size_bytes = size;
                    info.total_sectors = size / info.sector_size;
                }
                disks.push(info);
            }
        }

        // Also try system_profiler for additional drive information
        if let Ok(mut profiler_disks) = Self::enumerate_via_system_profiler() {
            disks.append(&mut profiler_disks);
        }

        Ok(disks)
    }

    /// Get detailed disk information using diskutil info
    fn get_disk_info(disk_id: &str) -> Result<DiskInfo, DiskError> {
        let output = Command::new("diskutil")
            .arg("info")
            .arg(disk_id)
            .output()
            .map_err(|_| DiskError::HardwareError)?;

        if !output.status.success() {
            return Err(DiskError::HardwareError);
        }

        let output_str = String::from_utf8_lossy(&output.stdout);
        let mut model = String::from("Unknown");
        let serial = String::from("Unknown");
        let mut size_bytes = 0u64;
        let mut interface = DiskInterface::ATA;
        let sector_size = 512u64;

        for line in output_str.lines() {
            let line = line.trim();
            
            if line.starts_with("Device / Media Name:") {
                if let Some(name) = line.split(':').nth(1) {
                    model = name.trim().to_string();
                }
            } else if line.starts_with("Volume Name:") {
                if model == "Unknown" {
                    if let Some(name) = line.split(':').nth(1) {
                        model = name.trim().to_string();
                    }
                }
            } else if line.starts_with("Disk Size:") {
                if let Some(size_str) = line.split(':').nth(1) {
                    size_bytes = Self::parse_size_bytes(size_str.trim());
                }
            } else if line.starts_with("Device Identifier:") {
                // Can extract disk identifier if needed
            } else if line.contains("Protocol:") {
                if line.contains("SATA") {
                    interface = DiskInterface::SATA;
                } else if line.contains("USB") {
                    interface = DiskInterface::USB;
                } else if line.contains("NVMe") || line.contains("PCIe") {
                    interface = DiskInterface::NVMe;
                }
            }
        }

        let total_sectors = if sector_size > 0 {
            size_bytes / sector_size
        } else {
            0
        };

        Ok(DiskInfo {
            interface,
            size_bytes,
            sector_size,
            total_sectors,
            model,
            serial,
            firmware: String::from("Unknown"),
        })
    }

    /// Enumerate disks using system_profiler
    fn enumerate_via_system_profiler() -> Result<Vec<DiskInfo>, DiskError> {
        let mut disks = Vec::new();

        let output = Command::new("system_profiler")
            .arg("SPStorageDataType")
            .output()
            .map_err(|_| DiskError::HardwareError)?;

        if !output.status.success() {
            return Err(DiskError::HardwareError);
        }

        let output_str = String::from_utf8_lossy(&output.stdout);
        let mut current_model = String::new();
        let mut current_size = 0u64;
        let mut current_interface = DiskInterface::ATA;

        for line in output_str.lines() {
            let line = line.trim();
            
            if line.starts_with("Device Name:") {
                if let Some(name) = line.split(':').nth(1) {
                    current_model = name.trim().to_string();
                }
            } else if line.starts_with("Capacity:") {
                if let Some(size_str) = line.split(':').nth(1) {
                    current_size = Self::parse_size_bytes(size_str.trim());
                }
            } else if line.starts_with("Protocol:") {
                if line.contains("SATA") {
                    current_interface = DiskInterface::SATA;
                } else if line.contains("USB") {
                    current_interface = DiskInterface::USB;
                } else if line.contains("NVMe") || line.contains("PCIe") {
                    current_interface = DiskInterface::NVMe;
                }
            } else if line.is_empty() && !current_model.is_empty() && current_size > 0 {
                // End of drive entry, create DiskInfo
                let sector_size = 512u64;
                let total_sectors = current_size / sector_size;
                
                disks.push(DiskInfo {
                    interface: current_interface,
                    size_bytes: current_size,
                    sector_size,
                    total_sectors,
                    model: current_model.clone(),
                    serial: String::from("Unknown"),
                    firmware: String::from("Unknown"),
                });
                
                current_model.clear();
                current_size = 0;
                current_interface = DiskInterface::ATA;
            }
        }

        Ok(disks)
    }

    /// Parse size string (e.g., "1.0 TB", "500 GB", "250 MB")
    fn parse_size(size_str: &str) -> Option<u64> {
        let bytes = Self::parse_size_bytes(size_str);
        if bytes > 0 {
            Some(bytes)
        } else {
            None
        }
    }

    /// Parse size bytes from string (e.g., "1.0 TB" -> bytes)
    fn parse_size_bytes(size_str: &str) -> u64 {
        let size_str = size_str.trim();
        
        // Remove asterisks and other markers
        let size_str = size_str.trim_start_matches('*').trim();
        
        // Try to parse number and unit
        let parts: Vec<&str> = size_str.split_whitespace().collect();
        if parts.len() < 2 {
            return 0;
        }

        let number_str = parts[0];
        let unit = parts[1].to_uppercase();

        let number: f64 = match number_str.parse() {
            Ok(n) => n,
            Err(_) => return 0,
        };

        let multiplier = match unit.as_str() {
            "B" | "BYTES" => 1u64,
            "KB" | "KILOBYTES" => 1024u64,
            "MB" | "MEGABYTES" => 1024u64 * 1024,
            "GB" | "GIGABYTES" => 1024u64 * 1024 * 1024,
            "TB" | "TERABYTES" => 1024u64 * 1024 * 1024 * 1024,
            _ => return 0,
        };

        (number * multiplier as f64) as u64
    }
}

