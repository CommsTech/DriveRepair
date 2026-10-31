// Native operating-system builds are deliberately non-destructive until the
// experimental Rust device drivers have undergone independent verification.
fn main() {
    println!("DriveRepair — host development launcher");
    println!(
        "The experimental boot firmware and low-level Rust repair code are not ready for real disks."
    );
    println!("For read-only external USB/disk scans without rebooting:");
    println!("  cd desktop");
    println!("  python3 -m driverepair_desktop list");
    println!("  python3 -m driverepair_desktop scan --device <ID-from-list>");
    println!("See desktop/README.md for Windows, macOS, Linux, permissions and warnings.");
    println!("No disk scanning or writing was performed by this launcher.");
}
