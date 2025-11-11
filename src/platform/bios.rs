// Platform-specific implementations for BIOS environment
// Direct port I/O using inline assembly

#![allow(dead_code)]

use crate::disk::DiskError;
use crate::platform::{MemoryIO, PciDevice, PciIO, PortIO};
use core::result::Result;

/// BIOS platform implementation
pub struct BiosPlatform;

impl PortIO for BiosPlatform {
    /// Read byte from I/O port (inline assembly)
    /// Note: This requires kernel privileges in Windows/Linux user mode
    fn inb(port: u16) -> u8 {
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        {
            let value: u8;
            unsafe {
                core::arch::asm!(
                    "in al, dx",
                    in("dx") port,
                    out("al") value,
                    options(nomem, nostack)
                );
            }
            value
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            // In user mode (Windows/Linux/macOS), port I/O requires kernel privileges
            // Return 0 as placeholder - actual implementation requires kernel driver
            let _port = port; // Suppress unused variable warning
            0
        }
    }

    /// Write byte to I/O port (inline assembly)
    fn outb(port: u16, value: u8) {
        #[cfg(target_arch = "x86_64")]
        unsafe {
            core::arch::asm!(
                "out dx, al",
                in("dx") port,
                in("al") value,
                options(nomem, nostack)
            );
        }
    }

    /// Read word (16-bit) from I/O port
    fn inw(port: u16) -> u16 {
        #[cfg(target_arch = "x86_64")]
        {
            let value: u16;
            unsafe {
                core::arch::asm!(
                    "in ax, dx",
                    in("dx") port,
                    out("ax") value,
                    options(nomem, nostack)
                );
            }
            value
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            0 // Placeholder for non-x86_64
        }
    }

    /// Write word (16-bit) to I/O port
    fn outw(port: u16, value: u16) {
        #[cfg(target_arch = "x86_64")]
        unsafe {
            core::arch::asm!(
                "out dx, ax",
                in("dx") port,
                in("ax") value,
                options(nomem, nostack)
            );
        }
    }

    /// Read double word (32-bit) from I/O port
    fn indw(port: u16) -> u32 {
        #[cfg(target_arch = "x86_64")]
        {
            let value: u32;
            unsafe {
                core::arch::asm!(
                    "in eax, dx",
                    in("dx") port,
                    out("eax") value,
                    options(nomem, nostack)
                );
            }
            value
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            0 // Placeholder for non-x86_64
        }
    }

    /// Write double word (32-bit) to I/O port
    fn outdw(port: u16, value: u32) {
        #[cfg(target_arch = "x86_64")]
        unsafe {
            core::arch::asm!(
                "out dx, eax",
                in("dx") port,
                in("eax") value,
                options(nomem, nostack)
            );
        }
    }

    /// Delay for specified microseconds
    fn delay_us(microseconds: u32) {
        // Simple delay loop
        // Note: This is a placeholder - actual timing depends on CPU frequency
        for _ in 0..microseconds {
            #[cfg(target_arch = "x86_64")]
            unsafe {
                core::arch::asm!("pause", options(nomem, nostack));
            }
        }
    }

    /// Delay for specified milliseconds
    fn delay_ms(milliseconds: u32) {
        Self::delay_us(milliseconds * 1000);
    }
}

impl MemoryIO for BiosPlatform {
    /// Read byte from memory-mapped I/O
    fn readb(address: u64) -> u8 {
        unsafe { core::ptr::read_volatile(address as *const u8) }
    }

    /// Write byte to memory-mapped I/O
    fn writeb(address: u64, value: u8) {
        unsafe { core::ptr::write_volatile(address as *mut u8, value) }
    }

    /// Read word from memory-mapped I/O
    fn readw(address: u64) -> u16 {
        unsafe { core::ptr::read_volatile(address as *const u16) }
    }

    /// Write word to memory-mapped I/O
    fn writew(address: u64, value: u16) {
        unsafe { core::ptr::write_volatile(address as *mut u16, value) }
    }

    /// Read double word from memory-mapped I/O
    fn readdw(address: u64) -> u32 {
        unsafe { core::ptr::read_volatile(address as *const u32) }
    }

    /// Write double word to memory-mapped I/O
    fn writedw(address: u64, value: u32) {
        unsafe { core::ptr::write_volatile(address as *mut u32, value) }
    }

    /// Read quad word from memory-mapped I/O
    fn readqw(address: u64) -> u64 {
        unsafe { core::ptr::read_volatile(address as *const u64) }
    }

    /// Write quad word to memory-mapped I/O
    fn writeqw(address: u64, value: u64) {
        unsafe { core::ptr::write_volatile(address as *mut u64, value) }
    }
}

impl PciIO for BiosPlatform {
    /// Read configuration space register
    fn read_config(bus: u8, device: u8, function: u8, offset: u8) -> u32 {
        #[cfg(target_arch = "x86_64")]
        {
            // PCI configuration space access via I/O ports 0xCF8 (address) and 0xCFC (data)
            let address: u32 = 0x80000000
                | ((bus as u32) << 16)
                | ((device as u32) << 11)
                | ((function as u32) << 8)
                | ((offset as u32) & 0xFC);

            BiosPlatform::outdw(0xCF8, address);
            BiosPlatform::indw(0xCFC) >> ((offset & 3) * 8) & 0xFF
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            0 // Placeholder for non-x86_64
        }
    }

    /// Write configuration space register
    fn write_config(bus: u8, device: u8, function: u8, offset: u8, value: u32) {
        #[cfg(target_arch = "x86_64")]
        {
            let address: u32 = 0x80000000
                | ((bus as u32) << 16)
                | ((device as u32) << 11)
                | ((function as u32) << 8)
                | ((offset as u32) & 0xFC);

            BiosPlatform::outdw(0xCF8, address);
            BiosPlatform::outdw(0xCFC, value);
        }
    }

    /// Enumerate PCI devices
    fn enumerate_devices() -> Result<Vec<PciDevice>, DiskError> {
        let mut devices = Vec::new();

        // Scan all PCI buses (0-255)
        for bus in 0..=255 {
            // Scan all devices on each bus (0-31)
            for device in 0..=31 {
                // Scan all functions on each device (0-7)
                for function in 0..=7 {
                    let vendor_id = Self::read_config(bus, device, function, 0x00) as u16;
                    let device_id = (Self::read_config(bus, device, function, 0x00) >> 16) as u16;

                    // Check if device exists (vendor ID 0xFFFF means no device)
                    if vendor_id != 0xFFFF {
                        let class_code =
                            (Self::read_config(bus, device, function, 0x08) >> 24) as u8;
                        let subclass = (Self::read_config(bus, device, function, 0x08) >> 16) as u8;
                        let prog_if = (Self::read_config(bus, device, function, 0x08) >> 8) as u8;

                        // Read base address registers
                        let mut base_address = [0u64; 6];
                        for (i, addr) in base_address.iter_mut().enumerate() {
                            let bar =
                                Self::read_config(bus, device, function, (0x10 + i * 4) as u8);
                            *addr = if (bar & 0x01) == 0 {
                                // Memory-mapped I/O
                                (bar & 0xFFFFFFF0) as u64
                            } else {
                                // I/O port
                                (bar & 0xFFFFFFFC) as u64
                            };
                        }

                        devices.push(PciDevice {
                            bus,
                            device,
                            function,
                            vendor_id,
                            device_id,
                            class_code,
                            subclass,
                            prog_if,
                            base_address,
                        });

                        // If function 0 and not a multi-function device, skip other functions
                        if function == 0 {
                            let header_type =
                                (Self::read_config(bus, device, function, 0x0C) >> 16) as u8;
                            if (header_type & 0x80) == 0 {
                                break; // Not a multi-function device
                            }
                        }
                    }
                }
            }
        }

        Ok(devices)
    }
}
