// Platform abstraction layer for low-level I/O operations
// Provides unified interface for port I/O across different platforms

#![allow(dead_code)]

use crate::disk::DiskError;
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// Platform-specific port I/O operations
pub trait PortIO {
    /// Read byte from I/O port
    fn inb(port: u16) -> u8;

    /// Write byte to I/O port
    fn outb(port: u16, value: u8);

    /// Read word (16-bit) from I/O port
    fn inw(port: u16) -> u16;

    /// Write word (16-bit) to I/O port
    fn outw(port: u16, value: u16);

    /// Read double word (32-bit) from I/O port
    fn indw(port: u16) -> u32;

    /// Write double word (32-bit) to I/O port
    fn outdw(port: u16, value: u32);

    /// Delay for specified microseconds
    fn delay_us(microseconds: u32);

    /// Delay for specified milliseconds
    fn delay_ms(milliseconds: u32);
}

/// Platform-specific memory operations
pub trait MemoryIO {
    /// Read byte from memory-mapped I/O
    fn readb(address: u64) -> u8;

    /// Write byte to memory-mapped I/O
    fn writeb(address: u64, value: u8);

    /// Read word from memory-mapped I/O
    fn readw(address: u64) -> u16;

    /// Write word to memory-mapped I/O
    fn writew(address: u64, value: u16);

    /// Read double word from memory-mapped I/O
    fn readdw(address: u64) -> u32;

    /// Write double word to memory-mapped I/O
    fn writedw(address: u64, value: u32);

    /// Read quad word from memory-mapped I/O
    fn readqw(address: u64) -> u64;

    /// Write quad word to memory-mapped I/O
    fn writeqw(address: u64, value: u64);
}

/// Platform-specific PCI operations
pub trait PciIO {
    /// Read configuration space register
    fn read_config(bus: u8, device: u8, function: u8, offset: u8) -> u32;

    /// Write configuration space register
    fn write_config(bus: u8, device: u8, function: u8, offset: u8, value: u32);

    /// Enumerate PCI devices
    fn enumerate_devices() -> Result<Vec<PciDevice>, DiskError>;
}

/// PCI device information
#[derive(Debug, Clone)]
pub struct PciDevice {
    pub bus: u8,
    pub device: u8,
    pub function: u8,
    pub vendor_id: u16,
    pub device_id: u16,
    pub class_code: u8,
    pub subclass: u8,
    pub prog_if: u8,
    pub base_address: [u64; 6],
}

impl PciDevice {
    /// Check if device matches class/subclass/prog_if
    pub fn matches(&self, class: u8, subclass: u8, prog_if: u8) -> bool {
        self.class_code == class && self.subclass == subclass && self.prog_if == prog_if
    }

    /// Check if device is NVMe controller
    pub fn is_nvme(&self) -> bool {
        self.matches(0x01, 0x08, 0x02) // Mass storage, Non-volatile memory, NVM Express
    }

    /// Check if device is AHCI controller
    pub fn is_ahci(&self) -> bool {
        self.matches(0x01, 0x06, 0x01) // Mass storage, SATA, AHCI
    }
}

/// Platform detection
pub enum Platform {
    /// BIOS environment (real mode or protected mode)
    Bios,
    /// UEFI environment
    Uefi,
    /// Windows OS
    Windows,
    /// Linux OS
    Linux,
    /// macOS
    MacOS,
}

/// Get current platform
pub fn get_platform() -> Platform {
    // TODO: Implement platform detection
    // For now, return a placeholder
    #[cfg(target_os = "windows")]
    return Platform::Windows;

    #[cfg(target_os = "linux")]
    return Platform::Linux;

    #[cfg(target_os = "macos")]
    return Platform::MacOS;

    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    Platform::Bios // Default to BIOS for bootable environments
}

pub mod bios;
pub mod uefi;
#[cfg(target_os = "windows")]
pub mod windows;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pci_device_matching() {
        let device = PciDevice {
            bus: 0,
            device: 1,
            function: 0,
            vendor_id: 0x8086,
            device_id: 0x1234,
            class_code: 0x01,
            subclass: 0x08,
            prog_if: 0x02,
            base_address: [0; 6],
        };

        assert!(device.is_nvme());
        assert!(!device.is_ahci());
    }
}
