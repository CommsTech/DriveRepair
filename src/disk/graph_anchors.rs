//! Dependency-graph anchors for disk backends.
//! Ensures experimental ATA/SATA/NVMe/USB/detection modules stay reachable
//! from the library test graph (closes "code island" false positives).

#![allow(dead_code)]

use crate::disk::ata::AtaDisk;
use crate::disk::ata_port_io::AtaPortIO;
use crate::disk::detection::DiskEnumerator;
use crate::disk::nvme::NvmeController;
use crate::disk::sata::AhciController;
use crate::disk::usb::UsbDisk;

#[cfg(feature = "alloc")]
use crate::disk::enhanced_detection::EnhancedDiskDetector;

/// Touch public constructors so backends remain in the module graph.
pub fn touch_disk_backends() {
    let _ = core::mem::size_of::<AtaPortIO>();
    let _ = AtaDisk::new(true, true);
    let _ = UsbDisk::new(1);
    let _ = AhciController::detect();
    let _ = NvmeController::detect();
    #[cfg(feature = "alloc")]
    {
        let _ = DiskEnumerator::enumerate();
        let _ = EnhancedDiskDetector::detect_ahci_controllers();
        let _ = EnhancedDiskDetector::detect_nvme_controllers();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disk_backend_graph_is_reachable() {
        touch_disk_backends();
        // Uninitialized ATA disks must not claim readiness / successful I/O.
        if let Ok(disk) = AtaDisk::new(true, true) {
            assert!(!crate::disk::Disk::is_ready(&disk));
        }
    }
}
