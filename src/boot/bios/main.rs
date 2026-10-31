#![no_std]
#![no_main]

//! Experimental BIOS boot binary — unshipped. Prefer `desktop/` scanner.

use core::panic::PanicInfo;

mod disk_detection;
mod disk_wrapper;
mod enhanced;
mod keyboard_input;
mod menu_integration;
mod repair_integration;

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

/// Keep experimental modules in the BIOS binary dependency graph.
#[allow(dead_code)]
fn touch_experimental_modules() {
    let _ = core::mem::size_of::<disk_detection::BiosDiskDetector>();
    let _ = core::mem::size_of::<disk_wrapper::BiosDisk>();
    let _ = core::mem::size_of::<keyboard_input::BiosKeyboardInput>();
    let _ = core::mem::size_of::<menu_integration::BiosMenuIntegration>();
    let _ = core::mem::size_of::<repair_integration::BiosRepairIntegration>();
    enhanced::touch();
}

#[no_mangle]
pub extern "C" fn _start() -> ! {
    touch_experimental_modules();
    // Explicit selection required — menu returns None until keyboard input exists.
    let _ = repair_integration::BiosRepairIntegration::run_repair_workflow();
    loop {}
}
