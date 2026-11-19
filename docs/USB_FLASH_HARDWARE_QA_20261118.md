# DriveRepair USB live-media flasher — operator handoff

**Status:** Code implemented, synthetic tests passed; **physical USB/Windows/BIOS/UEFI NOT VERIFIED**. Never use a patient disk to test this functionality.

## Why the original UI did not write a USB

The previous Tools → Bootable media builder action exported a ZIP containing the Debian live-ISO *build recipe*. It did not generate an ISO on Windows and did not write any USB device. The separate Build live ISO (Linux) action produced an ordinary hybrid ISO only on a Debian build host.

## New user flow

1. Build the DriveRepair Linux ISO in an isolated Debian build VM, or select an ISO hybrid built from a trusted source; validate its independently published SHA-256 before use. A ZIP build kit is **not** an ISO.
2. Connect a completely disposable USB stick, not a failing drive. Keep the ISO on a different physical disk.
3. Launch Qt → Tools → **Flash bootable USB**. Choose the `.iso`, then an enumerated USB whole disk. Windows uses a fresh Get-Disk gate; Linux verifies the mount and holder tree. Only external USB buses with hardware serials are offered.
4. Type `ERASE <exact selected device ID>`, accept permanent-loss warning, and confirm again. Windows must run elevated and obtain exclusive locks on every discoverable volume. Linux requires root and prior unmount of all partitions; the program will not mount/unmount arbitrary filesystems on the source.
5. Wait for **USB_FLASH_BYTE_VERIFIED_BOOT_UNTESTED**. The application writes an ISO-hybrid in bounded chunks, flushes and reads the entire image back, comparing SHA-256. Aborted or failed operations leave the USB **unusable/unverified**, with no rollback.
6. Independently boot the resulting USB in BIOS and UEFI VM, then on sacrificial physical hardware. Confirm DriveRepair opens, that no patient disk auto-mounts, storage enumeration works, and all rescue destinations remain separate. Record machine/vendor/firmware, USB bridge, Secure Boot state and results.

## Checks an agent with physical access MUST execute

- Confirm source file is a validated DriveRepair ISO-hybrid, not the exported build-kit ZIP or a normal non-hybrid ISO. Check checksum and test boot catalog using xorriso.
- Test ISO on a blank USB; verify only the selected USB partitions were destroyed. Ensure C: / system disk and every non-USB disk are excluded even when present.
- On Windows, attempt flashing a USB with normal mounted data; verify volumes lock/dismount, or fail clearly without writing if held open. Reinsert after flashing and read back checksum independently from another OS.
- Test wrong typed confirmation, changed USB identity, disconnect/reconnect, USB ID renumbering, read-only media, insufficient space, ISO located on the selected USB, lack of Administrator permissions and absent/misleading serial. All must refuse/abort without targeting another disk.
- Test WinError 5 and WinError 32 paths with occupied volumes; no forced bypass, deletion of other files or arbitrary diskpart changes.
- Interrupt at several points; verify no false success and that a partially written stick is explicitly labeled incomplete; never auto-retry destructive writes.
- Confirm OS reconnect behavior and proper handling of partitions with no drive letters/GUIDs, MSR, and unsupported mount paths.
- Verify USB boot under UEFI and legacy BIOS separately, plus installer/no-automount and recovery workflow smoke tests. Secure Boot compatibility is **unknown**, not assumed.
- Capture exact Windows version/driver, hardware serial suffix, controller, ISO SHA-256, output SHA-256 and successful boot evidence for the release gate.

## Existing scan stall in supplied logs

- `gui_debug_20261118T181410.log` stops on an investigation-phase 1 MiB read at byte **161,542,569,984** without a result. Neither successful repair nor successful cancel appears in the log.
- The earlier full-scan debug log finishes its scan around byte 499.9 GB and reports 178 read-error chunks; that is not evidence that in-place repair finished.
- `INVESTIGATING` and phase percentages are **attempt counts / plan estimates**, not completed data reconstruction. Driver/USB firmware may block synchronous reads even after the UI requests Stop. For precious source data, use rescue imaging first and avoid repeated stress.

## Scope / limitations

- USB flasher implements a deliberately distinct writer path from patient media refresh. It does not loosen patient repair restrictions. Whole USB content will be destroyed; it is NOT a recovery operation.
- The ISO-hybrid marker check only screens obviously incompatible files, not authenticity or guaranteed bootability. Checking release signatures is the operator's responsibility.
- The Windows writer reuses existing Win32 volume locking/write-through implementation; it has **not** run against real USB hardware here. Expect driver-specific failures, which must remain fail-closed.
- Python data transfer is used for this operator-controlled boot USB tool. Production performance and physical-disk I/O reliability still need real-hardware measurements.
