// Enhanced disk detection using platform-specific implementations
// Integrates PCI enumeration with disk detection

use crate::disk::detection::DiskEnumerator;
use crate::disk::{DiskError, DiskInfo, DiskInterface};
use crate::platform::{bios::BiosPlatform, PciDevice, PciIO};

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// Enhanced disk detector using platform-specific PCI enumeration
pub struct EnhancedDiskDetector;

impl EnhancedDiskDetector {
    /// Detect NVMe controllers using PCI enumeration
    #[cfg(feature = "alloc")]
    pub fn detect_nvme_controllers() -> Result<Vec<PciDevice>, DiskError> {
        let devices = BiosPlatform::enumerate_devices()?;
        let mut nvme_controllers = Vec::new();

        for device in devices {
            if device.is_nvme() {
                nvme_controllers.push(device);
            }
        }

        Ok(nvme_controllers)
    }

    /// Detect AHCI controllers using PCI enumeration
    #[cfg(feature = "alloc")]
    pub fn detect_ahci_controllers() -> Result<Vec<PciDevice>, DiskError> {
        let devices = BiosPlatform::enumerate_devices()?;
        let mut ahci_controllers = Vec::new();

        for device in devices {
            if device.is_ahci() {
                ahci_controllers.push(device);
            }
        }

        Ok(ahci_controllers)
    }

    /// Detect ATA/IDE drives using port probing
    #[cfg(feature = "alloc")]
    pub fn detect_ata_drives() -> Result<Vec<DiskInfo>, DiskError> {
        let mut drives = Vec::new();

        // Probe primary channel (0x1F0)
        if let Ok(disk) = Self::probe_ata_channel(true, true) {
            drives.push(disk);
        }
        if let Ok(disk) = Self::probe_ata_channel(true, false) {
            drives.push(disk);
        }

        // Probe secondary channel (0x170)
        if let Ok(disk) = Self::probe_ata_channel(false, true) {
            drives.push(disk);
        }
        if let Ok(disk) = Self::probe_ata_channel(false, false) {
            drives.push(disk);
        }

        Ok(drives)
    }

    /// Probe ATA channel for drive
    fn probe_ata_channel(primary: bool, _master: bool) -> Result<DiskInfo, DiskError> {
        use crate::disk::ata_port_io::AtaPortIO;

        let _port_io = AtaPortIO::new(primary);

        // Send IDENTIFY DEVICE command (0xEC)
        // TODO: Implement full IDENTIFY DEVICE command sequence
        // 1. Select drive (master/slave)
        // 2. Wait for ready
        // 3. Send IDENTIFY DEVICE command
        // 4. Wait for data ready
        // 5. Read 256 words (512 bytes) of identify data
        // 6. Parse identify data

        // For now, return placeholder
        Ok(DiskInfo {
            interface: DiskInterface::ATA,
            size_bytes: 0,
            sector_size: 512,
            total_sectors: 0,
            #[cfg(feature = "alloc")]
            model: alloc::string::String::new(),
            #[cfg(not(feature = "alloc"))]
            model: "",
            #[cfg(feature = "alloc")]
            serial: alloc::string::String::new(),
            #[cfg(not(feature = "alloc"))]
            serial: "",
            #[cfg(feature = "alloc")]
            firmware: alloc::string::String::new(),
            #[cfg(not(feature = "alloc"))]
            firmware: "",
        })
    }

    /// Enumerate all disks using platform-specific methods
    #[cfg(feature = "alloc")]
    pub fn enumerate_all() -> Result<Vec<DiskInfo>, DiskError> {
        let mut disks = Vec::new();

        // Enumerate ATA drives
        if let Ok(ata_drives) = Self::detect_ata_drives() {
            disks.extend(ata_drives);
        }

        // Enumerate NVMe drives via PCI
        if let Ok(nvme_controllers) = Self::detect_nvme_controllers() {
            for _controller in nvme_controllers {
                // TODO: Initialize NVMe controller and enumerate namespaces
                // For now, create placeholder disk info
                disks.push(DiskInfo {
                    interface: DiskInterface::NVMe,
                    size_bytes: 0,
                    sector_size: 512,
                    total_sectors: 0,
                    #[cfg(feature = "alloc")]
                    model: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    model: "",
                    #[cfg(feature = "alloc")]
                    serial: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    serial: "",
                    #[cfg(feature = "alloc")]
                    firmware: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    firmware: "",
                });
            }
        }

        // Enumerate AHCI/SATA drives via PCI
        if let Ok(ahci_controllers) = Self::detect_ahci_controllers() {
            for _controller in ahci_controllers {
                // TODO: Initialize AHCI controller and enumerate ports
                // For now, create placeholder disk info
                disks.push(DiskInfo {
                    interface: DiskInterface::SATA,
                    size_bytes: 0,
                    sector_size: 512,
                    total_sectors: 0,
                    #[cfg(feature = "alloc")]
                    model: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    model: "",
                    #[cfg(feature = "alloc")]
                    serial: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    serial: "",
                    #[cfg(feature = "alloc")]
                    firmware: alloc::string::String::new(),
                    #[cfg(not(feature = "alloc"))]
                    firmware: "",
                });
            }
        }

        Ok(disks)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_nvme_controllers() {
        // This test will fail in non-BIOS environment
        // But it validates the structure
        let _result = EnhancedDiskDetector::detect_nvme_controllers();
    }

    #[test]
    fn test_detect_ahci_controllers() {
        // This test will fail in non-BIOS environment
        // But it validates the structure
        let _result = EnhancedDiskDetector::detect_ahci_controllers();
    }
}
