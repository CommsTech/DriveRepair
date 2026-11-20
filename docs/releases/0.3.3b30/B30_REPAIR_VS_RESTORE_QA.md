# DriveRepair b30 — Repair/Restore Windows qualification

## What changed

**Repair drive** now has a distinct **Repair filesystem on selected drive (Windows)** operation that uses the native Windows `chkdsk.exe X: /f` procedure against a mapped *external* NTFS/FAT/exFAT volume. A model-specific SSD classification does not redirect users to image restoration. The existing **Targeted HDD region repair** remains a separate guarded procedure. **Restore data** contains imaging and salvage.

**Important:** filesystem metadata repair can modify allocation records and potentially lose access to damaged files. It is not SSD NAND repair, HDD reallocation, physical media rejuvenation, or proof that an entire drive is reliable. Run on a disposable or already-backed-up drive first.

## Windows hardware test checklist (sacrificial USB devices only)

1. In **Repair drive**, select a disposable SanDisk SSD/external flash device. Check that the default operation is Windows filesystem repair, **not** image rescue. Do not execute on any irreplaceable data.
2. Select a volume letter on that disk and confirm the app requires prior backup affirmation plus the exact `REPAIR E:`-style typed phrase. Confirm Cancel makes no write.
3. On a different physical disk select a volume letter that actually belongs elsewhere; the engine must refuse the mismatched `DiskNumber` before invoking CHKDSK.
4. Confirm OS boot/system disks, absent volumes, ambiguous disk numbers, RAW/ReFS filesystems, and incorrect identity hint all fail without invoking CHKDSK.
5. Run a **read-only plan** first using `repair-windows-filesystem --device ... --letter E --confirm-identity ... --json` and verify the reported volume belongs to the selected disk.
6. If the disposable filesystem has a reproducible *logical* metadata problem and a verified backup exists, authorize `CHKDSK /f` from the guarded beta. Inspect output and separately re-run a read-only check; review files directly and compare known-good checksums. No success claim should be made from the CHKDSK process exit alone.
7. While CHKDSK runs, check that the GUI reports Windows filesystem repair in progress, does not offer Stop, and does not forcibly terminate it on window close.
8. Test a busy volume: the app must not force a dismount (`/x`) or schedule repair at restart, and must report that repair was not confirmed.
9. Test **Targeted HDD region repair** with an independently verified sacrificial rotational disk. It must continue to require identity, external/bus confirmation, suitable media, journal, exclusive access and independent readback. SSD must NEVER enter this path.
10. Test the read-only public beta: attempting `repair-windows-filesystem --execute ...` must fail **before** touching the disk.
11. Confirm **Restore data** separately launches imaging/recovery without changing the Repair operation. Confirm both workspaces fit at common display sizes and the media-policy graphics reflect the selected workspace.

## Synthetic validation in this environment

- 577 pytest tests passed; 11 environment-dependent skips.
- Both public and guarded builds should be re-tested after packaging.
- No native PySide6 visual clickthrough, real Windows CHKDSK write operation, media remapping, or physical HDD repair was performed here.

## Known limitations

- SMART and device-inventory APIs can still fail behind certain USB bridges. Windows volume/disk binding permits *logical filesystem* repair when verified, but cannot prove physical media health.
- NTFS/exFAT/FAT mounted Windows volumes only for the new in-place logical repair path; unmounted/RAW volumes need a different offline workflow.
- CHKDSK does not reconstruct physically unreadable bytes. Disk failure, SSD wear or reallocation remain distinct hardware concerns.
- A storage-controller hang may leave Windows waiting for I/O; no user-mode utility can guarantee driver cancellation.
- A bootable recovery ISO with CPU/RAM diagnostics remains a separate hardware and boot-qualification item.
