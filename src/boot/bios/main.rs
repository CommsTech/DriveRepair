#![no_std]
#![no_main]

// BIOS bootloader entry point
// Multiboot-compliant bootloader for legacy BIOS systems

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

#[no_mangle]
pub extern "C" fn _start() -> ! {
    // TODO: Initialize BIOS bootloader
    // 1. Set up real mode stack
    // 2. Transition to protected mode
    // 3. Set up GDT and IDT
    // 4. Initialize VGA text mode
    // 5. Print welcome message: "DriveRepair by commstech v0.0.1"
    // 6. Initialize disk detection
    // 7. Enumerate disks
    // 8. Show disk list
    // 9. Prompt for disk selection
    // 10. Run repair
    
    loop {}
}

