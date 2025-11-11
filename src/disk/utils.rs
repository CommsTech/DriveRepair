// Utility functions for disk operations
// Helper functions for common disk operations and conversions

// Utility functions for disk operations

/// Convert bytes to sectors
pub fn bytes_to_sectors(bytes: u64, sector_size: u64) -> u64 {
    (bytes + sector_size - 1) / sector_size
}

/// Convert sectors to bytes
pub fn sectors_to_bytes(sectors: u64, sector_size: u64) -> u64 {
    sectors * sector_size
}

/// Convert CHS (Cylinder-Head-Sector) to LBA
///
/// # Arguments
/// * `cylinder` - Cylinder number (0-based)
/// * `head` - Head number (0-based)
/// * `sector` - Sector number (1-based)
/// * `heads_per_cylinder` - Number of heads per cylinder
/// * `sectors_per_track` - Number of sectors per track
pub fn chs_to_lba(
    cylinder: u32,
    head: u32,
    sector: u32,
    heads_per_cylinder: u32,
    sectors_per_track: u32,
) -> u64 {
    ((cylinder as u64 * heads_per_cylinder as u64 + head as u64) * sectors_per_track as u64
        + sector as u64)
        - 1
}

/// Convert LBA to CHS
///
/// # Arguments
/// * `lba` - Logical Block Address
/// * `heads_per_cylinder` - Number of heads per cylinder
/// * `sectors_per_track` - Number of sectors per track
pub fn lba_to_chs(lba: u64, heads_per_cylinder: u32, sectors_per_track: u32) -> (u32, u32, u32) {
    let sectors_per_cylinder = heads_per_cylinder as u64 * sectors_per_track as u64;
    let cylinder = (lba / sectors_per_cylinder) as u32;
    let temp = lba % sectors_per_cylinder;
    let head = (temp / sectors_per_track as u64) as u32;
    let sector = ((temp % sectors_per_track as u64) + 1) as u32;
    (cylinder, head, sector)
}

/// Validate LBA address
pub fn validate_lba(lba: u64, total_sectors: u64) -> bool {
    lba < total_sectors
}

/// Validate sector count
pub fn validate_sector_count(lba: u64, count: u32, total_sectors: u64) -> bool {
    lba + count as u64 <= total_sectors
}

/// Calculate disk size from sectors
pub fn calculate_disk_size(total_sectors: u64, sector_size: u64) -> u64 {
    total_sectors * sector_size
}

/// Format size for display (human-readable)
#[cfg(feature = "alloc")]
pub fn format_size_human(bytes: u64) -> alloc::string::String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB", "PB", "EB"];
    let mut size = bytes as f64;
    let mut unit_idx = 0;

    while size >= 1024.0 && unit_idx < UNITS.len() - 1 {
        size /= 1024.0;
        unit_idx += 1;
    }

    // Format with appropriate precision
    let precision = if size >= 100.0 {
        0
    } else if size >= 10.0 {
        1
    } else {
        2
    };

    let mut result = alloc::string::String::new();
    let int_part = size as u64;
    let frac_part = ((size - int_part as f64) * 100.0) as u32;

    // Convert int_part to string
    let mut n = int_part;
    if n == 0 {
        result.push('0');
    } else {
        let mut digits = alloc::vec::Vec::new();
        while n > 0 {
            digits.push((b'0' + (n % 10) as u8) as char);
            n /= 10;
        }
        for &digit in digits.iter().rev() {
            result.push(digit);
        }
    }

    if precision > 0 && frac_part > 0 {
        result.push('.');
        if precision == 2 && frac_part < 10 {
            result.push('0');
        }
        let mut n = frac_part;
        let mut digits = alloc::vec::Vec::new();
        while n > 0 && digits.len() < precision {
            digits.push((b'0' + (n % 10) as u8) as char);
            n /= 10;
        }
        for &digit in digits.iter().rev() {
            result.push(digit);
        }
    }

    result.push(' ');
    result.push_str(UNITS[unit_idx]);
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bytes_to_sectors() {
        assert_eq!(bytes_to_sectors(512, 512), 1);
        assert_eq!(bytes_to_sectors(513, 512), 2);
        assert_eq!(bytes_to_sectors(1024, 512), 2);
    }

    #[test]
    fn test_sectors_to_bytes() {
        assert_eq!(sectors_to_bytes(1, 512), 512);
        assert_eq!(sectors_to_bytes(2, 512), 1024);
    }

    #[test]
    fn test_chs_to_lba() {
        // First sector
        assert_eq!(chs_to_lba(0, 0, 1, 255, 63), 0);
        // Second sector
        assert_eq!(chs_to_lba(0, 0, 2, 255, 63), 1);
        // First sector of second head
        assert_eq!(chs_to_lba(0, 1, 1, 255, 63), 63);
    }

    #[test]
    fn test_lba_to_chs() {
        let (c, h, s) = lba_to_chs(0, 255, 63);
        assert_eq!(c, 0);
        assert_eq!(h, 0);
        assert_eq!(s, 1);
    }

    #[test]
    fn test_validate_lba() {
        assert!(validate_lba(0, 1000));
        assert!(validate_lba(999, 1000));
        assert!(!validate_lba(1000, 1000));
    }

    #[test]
    fn test_validate_sector_count() {
        assert!(validate_sector_count(0, 100, 1000));
        assert!(validate_sector_count(900, 100, 1000));
        assert!(!validate_sector_count(900, 101, 1000));
    }
}
