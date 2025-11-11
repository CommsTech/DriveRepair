// Standalone minimal UEFI bootloader - NO dependencies on drive-repair library
// DriveRepair by commstech v0.0.1

#![no_std]
#![no_main]

use uefi::prelude::*;
use uefi::table::SystemTable;

#[entry]
fn efi_main(_image: Handle, mut st: SystemTable<Boot>) -> Status {
    // Initialize UEFI services
    uefi_services::init(&mut st).unwrap();
    
    // Clear screen
    st.stdout().clear().unwrap();
    
    // Print welcome message using cstr16! macro
    st.stdout().output_string(cstr16!("DriveRepair by commstech v0.0.1\n")).unwrap();
    st.stdout().output_string(cstr16!("Drive Repair Tool - UEFI Edition\n")).unwrap();
    st.stdout().output_string(cstr16!("================================\n")).unwrap();
    st.stdout().output_string(cstr16!("Supports drives from 64GB to 20TB\n")).unwrap();
    st.stdout().output_string(cstr16!("ATA, SATA, NVMe, and USB support\n")).unwrap();
    st.stdout().output_string(cstr16!("x86_64 and ARM64 architectures\n")).unwrap();
    st.stdout().output_string(cstr16!("\n")).unwrap();
    st.stdout().output_string(cstr16!("Minimal bootloader - Boot successful!\n")).unwrap();
    st.stdout().output_string(cstr16!("\n")).unwrap();
    st.stdout().output_string(cstr16!("This is a test bootloader.\n")).unwrap();
    st.stdout().output_string(cstr16!("Full functionality coming soon.\n")).unwrap();
    st.stdout().output_string(cstr16!("\n")).unwrap();
    
    // Wait 5 seconds
    st.boot_services().stall(5_000_000);
    
    Status::SUCCESS
}
