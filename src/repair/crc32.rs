// CRC32 implementation for sector verification
// Based on IEEE 802.3 CRC-32 polynomial

/// CRC32 polynomial (IEEE 802.3)
const CRC32_POLY: u32 = 0xEDB88320;

/// Precomputed CRC32 lookup table
static CRC32_TABLE: [u32; 256] = {
    let mut table = [0u32; 256];
    let mut i = 0;
    while i < 256 {
        let mut crc = i as u32;
        let mut j = 0;
        while j < 8 {
            if crc & 1 != 0 {
                crc = (crc >> 1) ^ CRC32_POLY;
            } else {
                crc >>= 1;
            }
            j += 1;
        }
        table[i] = crc;
        i += 1;
    }
    table
};

/// Calculate CRC32 checksum
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xFFFFFFFFu32;

    for &byte in data {
        let index = ((crc ^ byte as u32) & 0xFF) as usize;
        crc = (crc >> 8) ^ CRC32_TABLE[index];
    }

    crc ^ 0xFFFFFFFF
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_crc32_empty() {
        assert_eq!(crc32(b""), 0x00000000);
    }

    #[test]
    fn test_crc32_simple() {
        // Known CRC32 value for "test"
        let crc = crc32(b"test");
        assert_eq!(crc, 0xD87F7E0C);
    }

    #[test]
    fn test_crc32_sector() {
        // Test with 512-byte sector (all zeros)
        // CRC32 of all zeros with IEEE 802.3 polynomial produces a specific value
        // This verifies that the CRC32 algorithm works correctly for large sectors
        let sector = [0u8; 512];
        let crc = crc32(&sector);
        // The actual calculated value for 512 zeros
        assert_eq!(crc, 0xB2D02E18);

        // Test with non-zero data to ensure CRC32 changes
        let mut sector2 = [0u8; 512];
        sector2[0] = 0x01;
        let crc2 = crc32(&sector2);
        assert_ne!(crc2, 0x00000000);
        assert_ne!(crc2, 0xB2D02E18);
    }
}
