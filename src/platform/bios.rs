// Platform-specific implementations for BIOS environment
// Gate 0: NEVER emit real in/out asm on windows/linux/macos (cargo test crash fix)

#![allow(dead_code)]

use crate::disk::DiskError;
use crate::platform::{MemoryIO, PciDevice, PciIO, PortIO};
use core::result::Result;

#[cfg(feature = "alloc")]
extern crate alloc;

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// True when running on a hosted OS where privileged port I/O is illegal
const fn is_hosted_os() -> bool {
    cfg!(any(target_os = "windows", target_os = "linux", target_os = "macos"))
}

/// BIOS platform implementation
pub struct BiosPlatform;

impl PortIO for BiosPlatform {
    /// Read byte from I/O port
    fn inb(port: u16) -> u8 {
        if is_hosted_os() {
            let _port = port;
            return 0;
        }
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
            let _port = port;
            0
        }
    }

    /// Write byte to I/O port
    fn outb(port: u16, value: u8) {
        if is_hosted_os() {
            let _ = (port, value);
            return;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        unsafe {
            core::arch::asm!(
                "out dx, al",
                in("dx") port,
                in("al") value,
                options(nomem, nostack)
            );
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _ = (port, value);
        }
    }

    /// Read word (16-bit) from I/O port
    fn inw(port: u16) -> u16 {
        if is_hosted_os() {
            let _port = port;
            return 0;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
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
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _port = port;
            0
        }
    }

    /// Write word (16-bit) to I/O port
    fn outw(port: u16, value: u16) {
        if is_hosted_os() {
            let _ = (port, value);
            return;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        unsafe {
            core::arch::asm!(
                "out dx, ax",
                in("dx") port,
                in("ax") value,
                options(nomem, nostack)
            );
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _ = (port, value);
        }
    }

    /// Read double word (32-bit) from I/O port
    fn indw(port: u16) -> u32 {
        if is_hosted_os() {
            let _port = port;
            return 0;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
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
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _port = port;
            0
        }
    }

    /// Write double word (32-bit) to I/O port
    fn outdw(port: u16, value: u32) {
        if is_hosted_os() {
            let _ = (port, value);
            return;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        unsafe {
            core::arch::asm!(
                "out dx, eax",
                in("dx") port,
                in("eax") value,
                options(nomem, nostack)
            );
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _ = (port, value);
        }
    }

    /// Delay for specified microseconds
    fn delay_us(microseconds: u32) {
        for _ in 0..microseconds {
            #[cfg(target_arch = "x86_64")]
            unsafe {
                // pause is not privileged; safe on hosted OS
                core::arch::asm!("pause", options(nomem, nostack));
            }
        }
    }

    /// Delay for specified milliseconds
    fn delay_ms(milliseconds: u32) {
        Self::delay_us(milliseconds.saturating_mul(1000));
    }
}

impl MemoryIO for BiosPlatform {
    fn readb(address: u64) -> u8 {
        if is_hosted_os() {
            let _ = address;
            return 0;
        }
        unsafe { core::ptr::read_volatile(address as *const u8) }
    }

    fn writeb(address: u64, value: u8) {
        if is_hosted_os() {
            let _ = (address, value);
            return;
        }
        unsafe { core::ptr::write_volatile(address as *mut u8, value) }
    }

    fn readw(address: u64) -> u16 {
        if is_hosted_os() {
            let _ = address;
            return 0;
        }
        unsafe { core::ptr::read_volatile(address as *const u16) }
    }

    fn writew(address: u64, value: u16) {
        if is_hosted_os() {
            let _ = (address, value);
            return;
        }
        unsafe { core::ptr::write_volatile(address as *mut u16, value) }
    }

    fn readdw(address: u64) -> u32 {
        if is_hosted_os() {
            let _ = address;
            return 0;
        }
        unsafe { core::ptr::read_volatile(address as *const u32) }
    }

    fn writedw(address: u64, value: u32) {
        if is_hosted_os() {
            let _ = (address, value);
            return;
        }
        unsafe { core::ptr::write_volatile(address as *mut u32, value) }
    }

    fn readqw(address: u64) -> u64 {
        if is_hosted_os() {
            let _ = address;
            return 0;
        }
        unsafe { core::ptr::read_volatile(address as *const u64) }
    }

    fn writeqw(address: u64, value: u64) {
        if is_hosted_os() {
            let _ = (address, value);
            return;
        }
        unsafe { core::ptr::write_volatile(address as *mut u64, value) }
    }
}

impl PciIO for BiosPlatform {
    fn read_config(bus: u8, device: u8, function: u8, offset: u8) -> u32 {
        if is_hosted_os() {
            let _ = (bus, device, function, offset);
            return 0xFFFF_FFFF; // no device
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        {
            let address: u32 = 0x80000000
                | ((bus as u32) << 16)
                | ((device as u32) << 11)
                | ((function as u32) << 8)
                | ((offset as u32) & 0xFC);

            BiosPlatform::outdw(0xCF8, address);
            BiosPlatform::indw(0xCFC) >> ((offset & 3) * 8) & 0xFF
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _ = (bus, device, function, offset);
            0xFFFF_FFFF
        }
    }

    fn write_config(bus: u8, device: u8, function: u8, offset: u8, value: u32) {
        if is_hosted_os() {
            let _ = (bus, device, function, offset, value);
            return;
        }
        #[cfg(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        ))]
        {
            let address: u32 = 0x80000000
                | ((bus as u32) << 16)
                | ((device as u32) << 11)
                | ((function as u32) << 8)
                | ((offset as u32) & 0xFC);

            BiosPlatform::outdw(0xCF8, address);
            BiosPlatform::outdw(0xCFC, value);
        }
        #[cfg(not(all(
            target_arch = "x86_64",
            not(any(target_os = "windows", target_os = "linux", target_os = "macos"))
        )))]
        {
            let _ = (bus, device, function, offset, value);
        }
    }

    /// Enumerate PCI devices
    fn enumerate_devices() -> Result<Vec<PciDevice>, DiskError> {
        if is_hosted_os() {
            // Hosted OS: do not probe ports; return empty list
            return Ok(Vec::new());
        }

        let mut devices = Vec::new();

        for bus in 0..=255 {
            for device in 0..=31 {
                for function in 0..=7 {
                    let vendor_id = Self::read_config(bus, device, function, 0x00) as u16;
                    let device_id = (Self::read_config(bus, device, function, 0x00) >> 16) as u16;

                    if vendor_id != 0xFFFF {
                        let class_code =
                            (Self::read_config(bus, device, function, 0x08) >> 24) as u8;
                        let subclass = (Self::read_config(bus, device, function, 0x08) >> 16) as u8;
                        let prog_if = (Self::read_config(bus, device, function, 0x08) >> 8) as u8;

                        let mut base_address = [0u64; 6];
                        for (i, addr) in base_address.iter_mut().enumerate() {
                            let bar =
                                Self::read_config(bus, device, function, (0x10 + i * 4) as u8);
                            *addr = if (bar & 0x01) == 0 {
                                (bar & 0xFFFFFFF0) as u64
                            } else {
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

                        if function == 0 {
                            let header_type =
                                (Self::read_config(bus, device, function, 0x0C) >> 16) as u8;
                            if (header_type & 0x80) == 0 {
                                break;
                            }
                        }
                    }
                }
            }
        }

        Ok(devices)
    }
}
