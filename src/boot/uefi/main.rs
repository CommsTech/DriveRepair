#![no_std]
#![no_main]

// UEFI bootloader entry point
// Main application for UEFI bootable environment

use uefi::prelude::*;
use uefi::table::boot::BootServices;
use uefi::table::SystemTable;
use uefi::Result;

#[entry]
fn efi_main(image: Handle, mut st: SystemTable<Boot>) -> Status {
    // Initialize UEFI services
    uefi_services::init(&mut st).unwrap();
    
    // Clear screen
    st.stdout().clear().unwrap();
    
    // Print welcome message
    st.stdout().output_string("DriveRepair by commstech v0.0.1\n").unwrap();
    st.stdout().output_string("Drive Repair Tool - UEFI Edition\n").unwrap();
    st.stdout().output_string("================================\n").unwrap();
    st.stdout().output_string("Supports drives from 64GB to 20TB\n").unwrap();
    st.stdout().output_string("ATA, SATA, NVMe, and USB support\n").unwrap();
    st.stdout().output_string("x86_64 and ARM64 architectures\n").unwrap();
    st.stdout().output_string("\n").unwrap();
    
    // Get boot services
    let bs = st.boot_services();
    
    // Run repair workflow
    use crate::boot::uefi::repair_integration::UefiRepairIntegration;
    let repair = UefiRepairIntegration::new(bs, &st);
    match repair.run_repair_workflow() {
        Ok(()) => {
            st.stdout().output_string("\nRepair workflow completed successfully.\n").unwrap();
            Status::SUCCESS
        }
        Err(e) => {
            st.stdout().output_string(&format!("ERROR: Repair failed: {:?}\n", e)).unwrap();
            e
        }
    }
}

