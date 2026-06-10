// macOS raw device disk access
// Uses /dev/rdisk* for direct sector access

#![cfg(all(target_os = "macos", feature = "std"))]

use crate::disk::{Disk, DiskError, DiskInfo};
use alloc::string::String;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};

/// macOS raw disk implementation using /dev/rdisk*
pub struct MacOSRawDisk {
    file: File,
    disk_info: DiskInfo,
    device_path: String,
}

impl MacOSRawDisk {
    /// Open raw disk device
    pub fn open(device_path: &str, info: DiskInfo) -> Result<Self, DiskError> {
        // Use raw device (rdisk) for direct access without buffering
        let raw_path = if device_path.starts_with("/dev/disk") {
            device_path.replace("/dev/disk", "/dev/rdisk")
        } else if device_path.starts_with("/dev/rdisk") {
            device_path.to_string()
        } else {
            return Err(DiskError::InvalidParameter);
        };

        // Validate disk info has valid sectors
        if info.total_sectors == 0 {
            eprintln!("Warning: disk_info has 0 sectors, size_bytes: {}", info.size_bytes);
        }

        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(&raw_path)
            .map_err(|e| {
                eprintln!("Failed to open {}: {:?}", raw_path, e);
                DiskError::HardwareError
            })?;

        eprintln!("Opened {} with {} sectors", raw_path, info.total_sectors);

        Ok(Self {
            file,
            disk_info: info, // disk_info is already owned, no clone needed
            device_path: raw_path,
        })
    }

    /// Create from disk identifier (e.g., "disk0")
    pub fn from_disk_id(disk_id: &str, info: DiskInfo) -> Result<Self, DiskError> {
        let device_path = format!("/dev/{}", disk_id);
        Self::open(&device_path, info)
    }
}

impl Disk for MacOSRawDisk {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(self.disk_info.clone())
    }

    fn read_sectors(&self, lba: u64, count: u32, buffer: &mut [u8]) -> Result<(), DiskError> {
        if lba + count as u64 > self.disk_info.total_sectors {
            return Err(DiskError::InvalidSector);
        }

        let sector_size = self.disk_info.sector_size;
        let offset = lba * sector_size;
        let bytes_to_read = (count as u64) * sector_size;

        if buffer.len() < bytes_to_read as usize {
            return Err(DiskError::InvalidParameter);
        }

        // Seek to sector position
        let mut file = &self.file;
        file.seek(SeekFrom::Start(offset))
            .map_err(|_| DiskError::ReadError)?;

        // Read sectors
        file.read_exact(&mut buffer[..bytes_to_read as usize])
            .map_err(|_| DiskError::ReadError)?;

        Ok(())
    }

    fn write_sectors(&self, lba: u64, count: u32, buffer: &[u8]) -> Result<(), DiskError> {
        if lba + count as u64 > self.disk_info.total_sectors {
            return Err(DiskError::InvalidSector);
        }

        let sector_size = self.disk_info.sector_size;
        let offset = lba * sector_size;
        let bytes_to_write = (count as u64) * sector_size;

        if buffer.len() < bytes_to_write as usize {
            return Err(DiskError::InvalidParameter);
        }

        // Open file for writing (need mutable reference)
        let mut file = OpenOptions::new()
            .write(true)
            .open(&self.device_path)
            .map_err(|_| DiskError::WriteError)?;

        // Seek to sector position
        file.seek(SeekFrom::Start(offset))
            .map_err(|_| DiskError::WriteError)?;

        // Write sectors
        file.write_all(&buffer[..bytes_to_write as usize])
            .map_err(|_| DiskError::WriteError)?;

        // Flush to ensure write is committed
        file.sync_all().map_err(|_| DiskError::WriteError)?;

        Ok(())
    }

    fn sector_size(&self) -> u64 {
        self.disk_info.sector_size
    }

    fn total_sectors(&self) -> u64 {
        self.disk_info.total_sectors
    }

    fn is_ready(&self) -> bool {
        true // File is open, so disk is ready
    }

    fn flush(&self) -> Result<(), DiskError> {
        // Open file and flush
        let file = OpenOptions::new()
            .write(true)
            .open(&self.device_path)
            .map_err(|_| DiskError::WriteError)?;
        file.sync_all().map_err(|_| DiskError::WriteError)?;
        Ok(())
    }
}

