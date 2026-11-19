# Recovering a failed system / boot drive

**Important:** The repository includes experimental BIOS/UEFI source, but no validated, universally bootable DriveRepair recovery image. A booted program that prints a success message does not prove it can enumerate or rescue NVMe/SATA/USB disks safely.

## Supported fallback using an independently trusted live environment

1. On a separate clean PC, prepare a trusted and verified Linux live USB from a maintained distribution. Follow the distribution's checksum/signature verification, not a homemade unsigned image.
2. Boot the affected computer without mounting or repairing the failing system volume. If the drive is physically noisy/unstable, avoid retries and consult a specialist.
3. Connect enough healthy destination space for an image; preferably a separate physical drive. Do not attempt to 'repair the only copy' by rewriting every sector.
4. Run the validated diagnostic/read-only commands from a mounted DriveRepair portable source environment, or a known recovery program. The current direct-physical `rescue-external` workflow is Linux experimental and verifies source/destination ancestry. If unable to confirm safe destination, use a separately validated imaging tool.
5. Preserve rescue maps and hash manifests off the patient. Analyze/repair a *copy* after acquisition.
6. Restore verified recovered files or a known-good system backup to replacement media. Reinstall the OS when needed.

Encryption: BitLocker, FileVault and LUKS require authorized credentials/keys; raw carving encrypted data usually yields false results. Secure Boot, RAID, vendor recovery partitions, BitLocker TPM binding and filesystem support must be tested individually.

## Experimental hybrid live-ISO build recipe (NOT BOOT-VERIFIED)

`./scripts/build_live_iso.sh /build/output` targets Debian trixie on x86-64
with GRUB-PC and GRUB-EFI via live-build. The package includes DriveRepair,
Python/Tk, smartctl, GNU ddrescue, testdisk and network mount tools.
It does NOT write to USB or patient media. The output is explicitly
`UNVERIFIED` until BIOS and UEFI VM and hardware boot tests pass. The
separately included bare-metal Rust boot code is NOT an established recovery OS.

See `ONE_DRIVE_RECOVERY.md` for the guided live-mode internal disk imaging
workflow, explicit source identity, NAS/USB destination, resume, and limitations.

## Future native boot goals (NOT IMPLEMENTED)

- Reproducible UEFI and BIOS media build with SHA-256 and verified boot smoke tests.
- Built-in OS storage drivers for NVMe, SATA, USB/UASP and SAS; no proprietary firmware bypass by default.
- Explicit no-automount, no-write environment, source/destination physical identity, USB disconnect handling.
- On-device manual recovery journal, encrypted report export and clear recovery/repair separation.

Do not make an untested ISO or USB writer available to beta users as a complete recovery product.
