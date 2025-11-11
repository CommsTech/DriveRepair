#![no_std]
#![no_main]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

#[no_mangle]
pub extern "C" fn _start() -> ! {
    // Run repair workflow
    use crate::boot::bios::repair_integration::BiosRepairIntegration;
    if let Err(_e) = BiosRepairIntegration::run_repair_workflow() {
        // Error already displayed
    }

    loop {}
}

