# DriveRepair — independent operator QA / unresolved hardware tests (2026-11-20)

## Scope / version

Apply the supplied source changes and **build a new ISO**. Existing ISO/USB media
are not modified by this patch. All tests are evidence collection; do not use
irreplaceable photos, system drives or your only backup as write targets.

## 1. Build and boot ISO — do this BEFORE any source disk repair

- [ ] Generate a fresh ISO with the updated recipe into an empty output directory.
- [ ] Confirm the generated ISO has the three **DriveRepair** boot options (not Debian defaults).
- [ ] Boot the ISO in a disposable **BIOS VM**; record which entry, boot, desktop,
      Qt launch, USB-disk enumeration, and whether it requested authentication.
- [ ] Boot the ISO in a disposable **UEFI VM**, repeat those checks.
- [ ] Test **normal graphical boot** on the HP laptop: record full model, CPU,
      firmware revision, legacy/UEFI selection, current Secure Boot state and
      exact last message/photograph on failure. Do not assume a boot freeze
      reflects damage to a patient drive.
- [ ] If graphical boot fails, test **Compatibility graphics** and record whether
      `nomodeset` changes the result; then test the text console only if needed.
- [ ] Confirm live desktop autologin as `driverepair` and automatic opening of
      Qt. If login is shown, record if `driverepair` / `live` works. Do not
      claim these are proven credentials before completing the test.
- [ ] Confirm no patient disks are mounted automatically, nor any raw write started.
- [ ] Confirm the ISO does **not** boot as a Debian installer, and verify the
      final .iso SHA-256 against its adjacent .sha256 file.
- [ ] Record Secure Boot outcome; no validation or bypass is implied by build success.

## 2. Windows USB-dock repair — use a disposable ROTATIONAL HDD only

- [ ] Run DriveRepair elevated in Windows when testing physical access.
- [ ] Select the intended `windows:PhysicalDriveN` and confirm model, unique
      serial suffix and exact current capacity. Disconnect/reconnect and check
      that fingerprint changes invalidate cached permissions.
- [ ] In Diagnose, obtain the SMART read-only health report (with exact
      `smartctl --version`, `smartctl --json --all /dev/pdN` and exact command arguments if it says "command line did
      not parse"). Record whether native Windows / ATA-IDENTIFY independently
      establishes that the drive actually rotates.
- [ ] For supported SATA-to-USB bridges, review SMART/SAT responses. Do not
      treat a model label or healthy Windows HealthStatus as permission to write.
- [ ] Select **Targeted HDD region repair**; confirm the UI stays on that option
      even if blocked and the reason is visible. Do not accept a surprise CHKDSK
      invocation. Separately select `Repair filesystem...` and verify it
      requires a specific matching NTFS/FAT/exFAT volume and confirmations.
- [ ] With a backed-up **disposable** HDD, separate durable journal, stable
      power and operator consent, test a bounded journaled repair and inspect
      lock/dismount, before/after reads, write count and rollback receipts.
      No physical write should occur without independent engine gates.
- [ ] Test an SSD/flash device: HDD magnetic rewrite must remain unavailable;
      do not try it as an SSD reconditioning method.
- [ ] Test USB disconnect, Windows busy volume, missing Admin rights, false
      PhysicalDrive mapping, blocked SMART probe, and cancellation. Expected:
      fail closed, no false success, no silently altered filesystem.

## 3. Cold-storage photos — on a COPY of the archive for tests

- [ ] Choose **Cold storage integrity** in the sidebar. Baseline a small copy
      of folders using a new JSON path on a separate device.
- [ ] Confirm file count progress increases and source file hashes do not
      change. Reconnect under another Windows drive letter and verify again.
- [ ] Flip a byte in a copy of one file; verify that file is marked **changed**.
- [ ] Add a legitimate photo; verify **new**, not corrupt. Delete one copy and
      verify **missing**. Simulate unreadable input and verify an error, not pass.
- [ ] Ensure old manifests are never silently overwritten. Manifests cannot
      restore lost bytes. Do not rotate away the only historic baseline.

## Remaining limitations

These changes do not deliver hardware validation, Secure Boot signing,
patient-side byte reconstruction, or proof of safe raw writes through an arbitrary
USB dock. Keep protected copies of irreplaceable files. Return screenshots,
command exit codes and redacted logs for follow-up.
