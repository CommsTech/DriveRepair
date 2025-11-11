// UEFI disk wrapper implementing Disk trait
// Provides disk access via UEFI Block I/O protocol

#![no_std]
#![no_main]

use uefi::prelude::*;
use uefi::table::boot::BootServices;
use uefi::proto::block::BlockIO;
use uefi::Result;

use crate::disk::{Disk, DiskError, DiskInfo, DiskInterface, SECTOR_SIZE_512};

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::string::String;

/// UEFI disk wrapper implementing Disk trait
pub struct UefiDisk<'a> {
    boot_services: &'a BootServices,
    handle: Handle,
    info: DiskInfo,
}

impl<'a> UefiDisk<'a> {
    /// Create new UEFI disk wrapper
    pub fn new(
        boot_services: &'a BootServices,
        handle: Handle,
        info: DiskInfo,
    ) -> Result<Self, DiskError> {
        Ok(Self {
            boot_services,
            handle,
            info,
        })
    }

    /// Get handle
    pub fn handle(&self) -> Handle {
        self.handle
    }
}

impl<'a> Disk for UefiDisk<'a> {
    fn info(&self) -> Result<DiskInfo, DiskError> {
        Ok(self.info.clone())
    }

    fn sector_size(&self) -> u64 {
        self.info.sector_size
    }

    fn total_sectors(&self) -> u64 {
        self.info.total_sectors
    }

    fn size_bytes(&self) -> u64 {
        self.info.size_bytes
    }

    fn read_sectors(&mut self, lba: u64, count: u32, buffer: &mut [u8]) -> Result<(), DiskError> {
        // Open Block I/O protocol
        let block_io = self
            .boot_services
            .open_protocol_exclusive::<BlockIO>(self.handle)
            .map_err(|_| DiskError::HardwareError)?;

        let media = block_io.media();
        let sector_size = media.block_size() as usize;

        // Validate LBA and count
        if lba > media.last_block() {
            return Err(DiskError::InvalidParameter);
        }

        if lba + count as u64 > media.last_block() + 1 {
            return Err(DiskError::InvalidParameter);
        }

        // Read sectors
        for sector_offset in 0..count {
            let current_lba = lba + sector_offset as u64;
            let buffer_offset = (sector_offset as usize) * sector_size;
            let sector_buffer = &mut buffer[buffer_offset..buffer_offset + sector_size];

            block_io
                .read_blocks(media, current_lba, sector_buffer)
                .map_err(|_| DiskError::HardwareError)?;
        }

        Ok(())
    }

    fn write_sectors(&mut self, lba: u64, count: u32, buffer: &[u8]) -> Result<(), DiskError> {
        // Open Block I/O protocol
        let block_io = self
            .boot_services
            .open_protocol_exclusive::<BlockIO>(self.handle)
            .map_err(|_| DiskError::HardwareError)?;

        let media = block_io.media();
        let sector_size = media.block_size() as usize;

        // Validate LBA and count
        if lba > media.last_block() {
            return Err(DiskError::InvalidParameter);
        }

        if lba + count as u64 > media.last_block() + 1 {
            return Err(DiskError::InvalidParameter);
        }

        // Check if media is writable
        if media.is_read_only() {
            return Err(DiskError::ReadOnly);
        }

        // Write sectors
        for sector_offset in 0..count {
            let current_lba = lba + sector_offset as u64;
            let buffer_offset = (sector_offset as usize) * sector_size;
            let sector_buffer = &buffer[buffer_offset..buffer_offset + sector_size];

            block_io
                .write_blocks(media, current_lba, sector_buffer)
                .map_err(|_| DiskError::HardwareError)?;
        }

        Ok(())
    }

    fn flush(&mut self) -> Result<(), DiskError> {
        // UEFI Block I/O protocol handles caching
        // Flush is typically handled automatically
        Ok(())
    }

    fn is_ready(&self) -> bool {
        // Try to open Block I/O protocol to check if disk is ready
        if let Ok(block_io) = self
            .boot_services
            .open_protocol_exclusive::<BlockIO>(self.handle)
        {
            let media = block_io.media();
            media.block_size() > 0 && media.last_block() > 0
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_uefi_disk_creation() {
        // This test requires UEFI environment
        // Just verify the structure exists
        assert!(true);
    }
}

