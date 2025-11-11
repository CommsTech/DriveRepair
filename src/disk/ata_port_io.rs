// Integration of platform-specific implementations with ATA disk module
// Provides platform-aware ATA disk access

use crate::disk::DiskError;
use crate::platform::{bios::BiosPlatform, PortIO};
use core::result::Result;

/// Platform-aware ATA register access
pub struct AtaPortIO {
    base_port: u16,
}

impl AtaPortIO {
    /// Create new ATA port I/O instance
    pub fn new(primary: bool) -> Self {
        Self {
            base_port: if primary { 0x1F0 } else { 0x170 },
        }
    }

    /// Read ATA register
    pub fn read_register(&self, offset: u16) -> Result<u8, DiskError> {
        let port = self.base_port + offset;

        // Use platform-specific port I/O
        // For BIOS: Use BiosPlatform
        // For UEFI: Use UEFI protocols (not direct port I/O)
        // For now, use BIOS implementation as default
        Ok(BiosPlatform::inb(port))
    }

    /// Write ATA register
    pub fn write_register(&self, offset: u16, value: u8) -> Result<(), DiskError> {
        let port = self.base_port + offset;

        // Use platform-specific port I/O
        BiosPlatform::outb(port, value);
        Ok(())
    }

    /// Wait for drive ready
    pub fn wait_ready(&self, _timeout_ms: u32) -> Result<(), DiskError> {
        let _start_time = 0; // TODO: Get current time
        let _timeout = _timeout_ms;
        
        loop {
            let status = self.read_register(7)?; // Status register
            
            // Check if BSY (bit 7) is clear and DRDY (bit 6) is set
            if (status & 0x80) == 0 && (status & 0x40) != 0 {
                return Ok(());
            }
            
            // Check for error
            if (status & 0x01) != 0 {
                let _error = self.read_register(1)?; // Error register
                return Err(DiskError::HardwareError);
            }
            
            // Check timeout
            // TODO: Implement actual timeout check
            BiosPlatform::delay_us(100); // 100 microseconds delay
        }
    }

    /// Read data from data register (16-bit words)
    pub fn read_data(&self, buffer: &mut [u16], count: usize) -> Result<(), DiskError> {
        let port = self.base_port; // Data register is at base port

        for word in buffer.iter_mut().take(count) {
            *word = BiosPlatform::inw(port);
        }

        Ok(())
    }

    /// Write data to data register (16-bit words)
    pub fn write_data(&self, buffer: &[u16], count: usize) -> Result<(), DiskError> {
        let port = self.base_port; // Data register is at base port

        for word in buffer.iter().take(count) {
            BiosPlatform::outw(port, *word);
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ata_port_io_creation() {
        let port_io = AtaPortIO::new(true);
        assert_eq!(port_io.base_port, 0x1F0);

        let port_io2 = AtaPortIO::new(false);
        assert_eq!(port_io2.base_port, 0x170);
    }
}
