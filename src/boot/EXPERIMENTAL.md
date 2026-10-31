# Experimental Boot Loaders (NOT SHIPPED)

The BIOS and UEFI homemade loaders under `src/boot/bios` and `src/boot/uefi` are
**experimental and unshipped**.

## Product recovery path

The intended recovery product path is a **Linux live ISO** with read-only-by-default
tooling, device identity checks, and off-source mapfile/journal support — not the
homemade BIOS/UEFI loaders.

## Gate 0 status

- Homemade boot menus must not auto-select disks or QuickScan without explicit input.
- Destructive USB provisioning scripts are **DISABLED** pending safety gates.
- Hardware backends (ATA/SATA/NVMe/USB) fail closed with `Unsupported`.
- Hosted OS builds never execute privileged port I/O (prevents `STATUS_PRIVILEGED_INSTRUCTION`).

## NOT_PROVEN

- Boot ISO build in CI
- Real AHCI/NVMe/ATA identify and I/O on bare metal
- End-to-end rescue against physical media
