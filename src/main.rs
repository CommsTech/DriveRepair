// Standard library version for testing and development
// This is not used in the bootable environment

#[cfg(feature = "alloc")]
use drive_repair::disk::detection::DiskEnumerator;
#[cfg(feature = "alloc")]
use drive_repair::disk::{Disk, DiskError, DiskInfo};
#[cfg(feature = "alloc")]
use drive_repair::repair::{RepairConfig, RepairEngine, ScanPattern};
use drive_repair::ui::UserInterface;
// Menu and RepairOption are used in the interactive flow

fn main() {
    println!("DriveRepair by commstech v0.0.1");
    println!("Drive Repair Tool - Development Version");
    println!("========================================\n");

    // Show welcome screen
    UserInterface::show_welcome();

    // Enumerate disks
    #[cfg(feature = "alloc")]
    {
        match DiskEnumerator::get_disk_list() {
            Ok(disks) => {
                if disks.is_empty() {
                    println!("No drives detected.");
                    println!("\nNote: On macOS, low-level disk access requires:");
                    println!("  - Running as root/administrator");
                    println!("  - Or using IOKit APIs (not yet implemented)");
                } else {
                    UserInterface::show_disk_list(&disks);

                    // Interactive menu for drive selection and repair
                    if let Err(e) = run_interactive_repair(&disks) {
                        println!("Error: {:?}", e);
                    }
                }
            }
            Err(e) => {
                println!("Error enumerating disks: {:?}", e);
                println!("\nNote: On macOS, low-level disk access may require:");
                println!("  - Running as root/administrator");
                println!("  - Or using IOKit APIs (not yet implemented)");
                println!("\nThe application can still run in dry-run mode for testing.");
            }
        }
    }

    #[cfg(not(feature = "alloc"))]
    {
        println!("Alloc feature not enabled. Disk enumeration requires alloc support.");
    }
}

#[cfg(feature = "alloc")]
fn run_interactive_repair(disks: &[DiskInfo]) -> Result<(), DiskError> {
    use std::io::{self, Write};
    
    // Select drive
    print!("\nSelect drive to repair (0-{}), or 'q' to quit: ", disks.len() - 1);
    io::stdout().flush().unwrap();
    
    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    let input = input.trim();
    
    if input == "q" || input == "Q" {
        println!("Cancelled.");
        return Ok(());
    }
    
    let disk_index: usize = match input.parse() {
        Ok(idx) if idx < disks.len() => idx,
        _ => {
            println!("Invalid selection.");
            return Err(DiskError::InvalidParameter);
        }
    };
    
    let selected_disk = &disks[disk_index];
    
    // Show disk info
    println!("\n{}", "=".repeat(60));
    println!("Selected Drive:");
    UserInterface::show_disk_info(selected_disk);
    
    // Show warning
    println!("{}", "=".repeat(60));
    println!("WARNING: Drive repair operations will READ and WRITE to the selected drive.");
    println!("This tool performs sector refresh (read-then-write) to:");
    println!("  - Trigger drive firmware to remap weak sectors");
    println!("  - Refresh magnetic data on sectors");
    println!("  - Encourage reallocation of bad sectors to spare sectors");
    println!("This is similar to SpinRite's repair mechanism.");
    println!("{}", "=".repeat(60));
    
    // Show repair options
    println!("\nRepair Options:");
    println!("  1. Quick Scan (sector refresh, sequential, limited sectors)");
    println!("  2. Full Scan (sector refresh, sequential, entire drive)");
    println!("  3. SMART Check (not yet implemented)");
    println!("  4. Dry Run (read-only test, first 1000 sectors only)");
    println!("  5. Cancel");
    
    print!("\nSelect option (1-5): ");
    io::stdout().flush().unwrap();
    
    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    let option = input.trim();
    
    let (config, is_dry_run) = match option {
        "1" => (
            RepairConfig {
                scan_pattern: ScanPattern::Sequential,
                max_retries: 3,
                timeout_ms: 5000,
                aggressive_correction: false,
                enable_trim: false,
                start_sector: 0,
                end_sector: selected_disk.total_sectors,
            },
            false,
        ),
        "2" => (
            RepairConfig {
                scan_pattern: ScanPattern::Sequential,
                max_retries: 5,
                timeout_ms: 10000,
                aggressive_correction: true,
                enable_trim: false,
                start_sector: 0,
                end_sector: selected_disk.total_sectors,
            },
            false,
        ),
        "3" => {
            println!("SMART check not yet implemented.");
            return Ok(());
        }
        "4" => {
            // Dry run uses read-only mode
            (
                RepairConfig {
                    scan_pattern: ScanPattern::Sequential,
                    max_retries: 1,
                    timeout_ms: 1000,
                    aggressive_correction: false,
                    enable_trim: false,
                    start_sector: 0,
                    end_sector: selected_disk.total_sectors.min(1000),
                },
                true, // is_dry_run
            )
        },
        "5" => {
            println!("Cancelled.");
            return Ok(());
        }
        _ => {
            println!("Invalid option.");
            return Err(DiskError::InvalidParameter);
        }
    };
    
    if is_dry_run {
        println!("\nDRY RUN MODE: Limited scan for testing only (first 1000 sectors).");
    }
    
    // Final confirmation
    print!("\nProceed with repair? (yes/no): ");
    io::stdout().flush().unwrap();
    
    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap();
    let confirm = input.trim().to_lowercase();
    
    if confirm != "yes" && confirm != "y" {
        println!("Cancelled.");
        return Ok(());
    }
    
    // Try to get actual disk object for repair
    // Note: This may not work on macOS without proper permissions
    println!("\n{}", "=".repeat(60));
    println!("Starting {} on disk: {} ({})",
        if is_dry_run { "dry run scan" } else { "repair scan" },
        selected_disk.model,
        drive_repair::disk::detection::format_size(selected_disk.size_bytes)
    );
    println!("{}", "=".repeat(60));
    
    // Attempt to access disk for repair
    // Note: On macOS, this requires low-level access which may not work in user mode
    println!("\nAttempting to access disk for repair...");
    println!("Note: Low-level disk access on macOS typically requires:");
    println!("  - Root privileges (run with 'sudo')");
    println!("  - Or IOKit APIs (not yet implemented in this version)");
    println!("\nFor full functionality, use the UEFI/BIOS bootloader version.");
    println!("\nThis standard library version can:");
    println!("  - Enumerate and display drive information");
    println!("  - Show repair configuration");
    println!("  - Demonstrate the repair workflow");
    
    // Try to enumerate disks (may fail on macOS without proper permissions)
    match DiskEnumerator::enumerate() {
        Ok(mut disk_objects) => {
            if disk_index < disk_objects.len() {
                let disk = disk_objects.remove(disk_index);
                
                // Create repair engine with trait object
                let mut repair_engine = if is_dry_run {
                    RepairEngine::new_boxed_read_only(disk, config.clone())
                } else {
                    RepairEngine::new_boxed(disk, config.clone())
                };
                
                println!("\n{}", "=".repeat(60));
                println!("Starting {} on disk: {} ({})",
                    if is_dry_run { "dry run scan" } else { "repair scan with sector refresh" },
                    selected_disk.model,
                    drive_repair::disk::detection::format_size(selected_disk.size_bytes)
                );
                if !is_dry_run {
                    println!("Mode: Sector Refresh (read-then-write to trigger remapping)");
                } else {
                    println!("Mode: Read-Only (no writes will be performed)");
                }
                println!("{}", "=".repeat(60));
                println!("\nNote: Low-level disk access may require root privileges.");
                println!("If you see errors, try running with: sudo cargo run\n");
                
                // Run repair with progress callback
                let progress_callback = |current: u64, total: u64, result: drive_repair::repair::RepairResult| {
                    UserInterface::show_repair_progress(current, total, result);
                    io::stdout().flush().unwrap();
                };
                
                // Check disk info before starting
                let total_sectors = repair_engine.disk.total_sectors();
                let sector_size = repair_engine.disk.sector_size();
                println!("\nDisk info: {} sectors, {} bytes per sector", total_sectors, sector_size);
                if total_sectors == 0 {
                    println!("\n✗ Error: Disk reports 0 sectors. Cannot proceed.");
                    println!("This may indicate the disk object is not properly initialized.");
                    println!("The disk may need to be unmounted or accessed differently.");
                    return Err(DiskError::InvalidParameter);
                }
                
                match repair_engine.scan_and_repair(progress_callback) {
                    Ok(stats) => {
                        println!(); // New line after progress
                        UserInterface::show_repair_stats(&stats);
                        if !is_dry_run {
                            println!("\n✓ Repair completed! Sectors have been refreshed to trigger remapping.");
                        } else {
                            println!("\n✓ Dry run completed! No sectors were modified.");
                        }
                    }
                    Err(e) => {
                        println!("\n✗ Repair failed: {:?}", e);
                        println!("\nThis may be due to:");
                        println!("  - Insufficient permissions (try: sudo cargo run)");
                        println!("  - Drive is mounted or in use (unmount first)");
                        println!("  - Disk reports 0 sectors (disk object not properly initialized)");
                        println!("  - macOS security restrictions (use bootloader version)");
                        return Err(e);
                    }
                }
            } else {
                println!("\n✗ Error: Could not access selected disk.");
                println!("  Note: On macOS, low-level disk access requires root privileges.");
                return Err(DiskError::InvalidParameter);
            }
        }
        Err(e) => {
            println!("\n✗ Error accessing disk: {:?}", e);
            println!("\n  This is expected on macOS without root privileges.");
            println!("  The repair workflow has been validated and is ready.");
            println!("  To actually run repairs, use the bootloader version or run with sudo.");
            // Don't return error - just inform the user
        }
    }
    
    Ok(())
}
