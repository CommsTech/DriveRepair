// Enhanced UEFI helpers — experimental / unshipped.
// Wired into the UEFI crate module graph; not a second EFI entry point.

use uefi::prelude::*;
use uefi::table::SystemTable;

/// Print the experimental UEFI banner (no disk mutation).
pub fn print_experimental_banner(st: &mut SystemTable<Boot>) -> Status {
    let _ = st.stdout().clear();
    let _ = st
        .stdout()
        .output_string(cstr16!("DriveRepair — experimental UEFI helpers\n"));
    let _ = st.stdout().output_string(cstr16!(
        "Homemade firmware path is unshipped. Prefer desktop/ read-only scanner.\n"
    ));
    Status::SUCCESS
}
