// Standard library version for testing and development
// This is not used in the bootable environment

#[cfg(feature = "alloc")]
use drive_repair::disk::detection::DiskEnumerator;
use drive_repair::ui::UserInterface;

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
                } else {
                    UserInterface::show_disk_list(&disks);
                }
            }
            Err(e) => {
                println!("Error enumerating disks: {:?}", e);
            }
        }
    }
    
    #[cfg(not(feature = "alloc"))]
    {
        println!("Alloc feature not enabled. Disk enumeration requires alloc support.");
    }
}

