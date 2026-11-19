# b21: Native Windows QA and release gates

## Changes and verification boundaries

The Qt workstation now has tabbed findings/visualization, a live-only setup collapse, a targeted error recheck and a Windows Debian WSL build path. Automated tests use synthetic readers and process mocks; **there is no claim of real-drive repair, boot success, or new neural reconstruction.**

### Native UI / layout (test 100%, 125%, 150%, 200% display scaling)

1. Run GUI at 1280×720, 1366×768, 1920×1080; assert no indispensable control is clipped, and no unnecessary main-panel scrolling at normal scale. A scrollbar may remain at high DPI/accessibility scaling rather than hiding controls.
2. In Diagnose, before Start, inspect the compact source, task and assessment. Start a sacrificial read-only quick scan. Source/task setup must disappear while the active session and **Surface map & throughput** tab appear. Stop must remain visible. After completion, source/task selection returns and **Assessment** opens automatically.
3. After a scan with recorded failures, `Address scan errors…` must show (a) reuse known bad read addresses with no whole-disk rescan, or (b) rescue-to-image. Confirm device disconnect/reorder invalidates the stored scan identity and blocks the action. Verify the CLI never opens a write handle.
4. No fabricated coverage: unique successful read coverage may differ from whole-job progress; zero errors is not a lifetime estimate.
5. Test out-of-date/empty scan reports, no SMART, USB transient removal and protected folder paths. Confirm no GUI freeze or command-line argument injection.

### SMART on Windows / external USB

1. Supply vetted official `smartctl.exe` and accompanying `smartctl.sha256` in `tools/smartmontools` adjacent to `.pyz`; confirm it is found without PATH entries. Replace 1 byte and confirm manifest check fails closed.
2. With no companion and no installed tool, **Enable SMART tools** must request consent and run Windows Package Manager in a nonblocking process. No silent executable download or unauthorized privilege action is allowed.
3. Test SATA direct connection, USB-SAT bridge, NVMe USB bridge, no-passthrough bridge, disconnected drive and serial-less drive. Verify physical repair remains unavailable when media identification, SMART, stable serial, exclusive access or journal preconditions are missing. Do NOT bypass the gate to manufacture a passing test.
4. Respect upstream smartmontools GPL license and corresponding-source requirements when shipping binary packages. A local checksum alone does not establish authenticity.

### Create recovery USB on Windows

1. `wsl -l -v` must show Debian (WSL2). If missing, the GUI must give the one-time Windows setup instruction and never silently install it.
2. With explicit operator consent, build on Debian WSL using the native Linux filesystem and check `lb`, debootstrap and xorriso. Confirm package installation happens only after approval. Use a brand-new empty destination folder. Re-running must not overwrite an existing ISO.
3. Confirm produced image has valid ISO9660/El Torito structures, a live kernel, initramfs, squashfs and BIOS/UEFI boot entries. Confirm the SHA-256 file. **These file checks do not prove bootability.**
4. Boot image in both SeaBIOS and OVMF UEFI VMs. Confirm GUI launches, disks enumerate, no patient is auto-mounted, and live recovery writes only to a distinct destination.
5. Flash only to a disposable USB with independent backup; type the exact device confirmation and select the conspicuous erase acknowledgement. Read back ISO bytes; then boot on physical BIOS and UEFI machines. Review Secure Boot separately; do not promise compatibility without tests.

### Hardware recovery qualification

Use sacrificial CMR, SMR, SSD, NVMe USB, and generic flash media. Record model, firmware, interface, SMART before/after, read-error locations, bytes recovered to a separate destination, repeat-read hashes, bridge disconnects, job time and whether a physical write occurred. Confirm weak-region HDD maintenance only after verified rotational media, backup, per-device consent, separate durable journal, locks, identity and postverify. Validate power interruption recovery **only on nonvaluable sacrificial disks**.
