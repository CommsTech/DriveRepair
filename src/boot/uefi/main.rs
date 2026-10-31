#![no_std]
#![no_main]

//! Experimental UEFI application binary — unshipped.
//! Wires disk/menu/repair/keyboard modules into one dependency graph.

use uefi::prelude::*;
use uefi::table::SystemTable;

mod disk_enumeration;
mod disk_wrapper;
mod enhanced;
mod keyboard_input;
mod menu_integration;
mod repair_integration;

/// Keep experimental helper modules in the binary dependency graph.
#[allow(dead_code)]
fn touch_experimental_modules() {
    let _ = core::mem::size_of::<keyboard_input::UefiKeyboardInput>();
    let _ = core::mem::size_of::<disk_enumeration::UefiDiskEnumerator>();
    let _ = core::mem::size_of::<menu_integration::UefiMenuIntegration>();
    let _ = core::mem::size_of::<repair_integration::UefiRepairIntegration>();
}

#[entry]
fn efi_main(_image: Handle, mut st: SystemTable<Boot>) -> Status {
    if uefi_services::init(&mut st).is_err() {
        return Status::LOAD_ERROR;
    }

    touch_experimental_modules();
    let _ = enhanced::print_experimental_banner(&mut st);

    // Explicit operator selection required inside repair workflow (no auto disk 0).
    let bs = st.boot_services();
    let repair = repair_integration::UefiRepairIntegration::new(bs, &st);
    match repair.run_repair_workflow() {
        Ok(()) => Status::SUCCESS,
        Err(e) => e,
    }
}
