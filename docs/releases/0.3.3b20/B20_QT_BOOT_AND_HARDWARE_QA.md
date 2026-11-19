# DriveRepair v0.3.3b20 — Windows / Linux qualification handoff

## Engineering scope and current truth

This revision eliminates the Tk desktop entry point and source from the application package. The Qt frontend now exposes most historical image/forensic/clone operations and separate read-only hardware diagnostics through the unchanged CLI engine. **This does not establish complete feature parity** with every obsolete Tk experimental option. Expert CLI access remains for niche operations (RAM-only refresh, offline-system in-place refresh, specialized monitoring), and their Qt UX requires further verification. Do not claim them fully migrated.

The previous USB wizard accepted any file having an MBR 0x55AA signature and ISO9660 `CD001`. This is not evidence of a bootable recovery operating system. `boot_validation.qualify_live_iso()` now verifies the ISO9660 directory records and expected live kernel, initramfs, root squashfs, hybrid partition record, and BIOS+UEFI boot catalog entries. It is called before real USB flash and before release sidecar packaging, and by local ISO auto-selection. Failing this check blocks physical flashing instead of writing an unusable image. A passed check is **not** a verified boot.

## Required test gates on a sacrificial lab machine

1. Prepare a clean Debian trixie x86-64 VM with `live-build`, `debootstrap`, `xorriso` and `python3`; run `sudo bash scripts/build_live_iso.sh /fresh/output`. The output must be a full live system, not a 32 MiB bootloader-only ISO. Run `bash scripts/check_live_iso.sh /fresh/output/*.iso` and inspect its JSON evidence.
2. Boot the resulting ISO in disposable **BIOS** and **UEFI** VMs. Verify boot menu, live desktop, actual `driverepair gui` Qt startup, and read-only default for patient volumes. Check with and without Secure Boot as appropriate; UEFI boot without Secure Boot does not certify Secure Boot.
3. **Only then** flash a sacrificial empty USB stick from Windows Qt. Verify the destructive checkbox has visible state, target fingerprint is correct, completion reports exact byte readback, and repeated boots succeed on physical UEFI and legacy BIOS machines if supported. USB may not show a Windows Explorer volume due to ISO-hybrid partitioning; use disk/partition inspection and actual boot, not Explorer emptiness, as verdicts.
4. Confirm the 32 MiB suspected placeholder ISO is now rejected **before** any drive is opened for writing. Test a truncated, symlink, fake-ISO and corrupt-boot-catalog file. Existing USB sticks flashed with a placeholder must be re-imaged with a real validated ISO.
5. Launch `gui`, `qt-gui` and legacy alias with PySide6 installed: all must open Qt. Verify Specialist tools: FAT32 and Sleuth Kit deleted-file preview/extraction, filesystem-signature detection, `recover-image`, `carve-image`, ZIP salvage, SHA-256 evidence/baseline/audit, independently trusted reference restore, and ext repair on new clone. Verify each new output refuses overwriting source or preexisting evidence.
6. Verify hardware diagnostics on a sacrificial USB bridge: `smartctl` installed, identify Seagate ST1000LM048, SMART rotation health, firmware, controller capabilities, sample benchmark and failed-offset probe. If SMART/rotation is hidden, **repair must remain ineligible**, but the GUI must explain why and route to read-only rescue. Do not bypass identity or SMART checks to make a button green.
7. Perform real physical-write testing on sacrificial **confirmed rotational** HDDs with a fresh separate verified journal and OS exclusive volume access. Test a complete repair, interrupted read, stolen disk identity, USB disconnect, power loss (simulated on disposable drives), postwrite SHA-256 comparison and SMART before/after. No write passes on SSD, NVMe, flash or unknown media.
8. Visual QA at 1366×768, 1920×1080 and 125–200% Windows scaling: idle dashboard not bloated, tool selection keyboard accessible, empty states meaningful, progress does not claim untested capacity, readable contrast for checkbox/danger buttons, no clipped forms, expert logs collapsed by default, safe Stop behavior.
9. Review parity gaps: old Tk had advanced RAM-only and journal-backend selectors, last-resort offline-system refresh, and selected recovery utilities. Current Qt specialist and device toolbox cover the major image/forensic paths; remaining rare high-risk workflows must be separately designed, tested and audited before declaring 100% parity.

## Environment and evidence limitations

- Synthetic Python test suite and zipapp CLI smoke can be run on the build host. Qt rendering and actual Windows device access require a Windows test VM/host with PySide6.
- No ISO artifact is included in the source ZIP; a Debian live image must be built separately and genuinely boot-tested.
- Rewriting repeatedly readable HDD sectors does not restore unreadable bytes, physically damaged heads or a proven reliable service life.
- Do not run write/restore USB authenticity tests on valuable patient data. A fraudulent flash translation layer may corrupt unrelated regions despite journal restoration.
