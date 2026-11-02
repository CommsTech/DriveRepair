# Windows volume preparation and bounded read-error boundaries (0.3.3b11)

## What users see

When an external disk has an assigned drive letter, the Qt **Fix my drive** workflow explains that DriveRepair can *attempt* to prepare it for in-place changes. Consent is collected before any physical write. A separate disk-identification fingerprint and explicit risk acknowledgement remain required. If Windows finds any open files or cannot verify device identity, preparation fails and **no write is authorized**.

DriveRepair does **not** blindly remove letters, force-dismount busy volumes, offline a disk, or interfere with system/boot/pagefile volumes. The preexisting external-disk identity checks remain authoritative. The new `--auto-lock-volumes` flag is opt-in and is available only to raw-drive write commands (`care-external` and `refresh-external`). It does not affect imaging, scanning or image-file operations.

Windows `FSCTL_LOCK_VOLUME` must succeed before `FSCTL_DISMOUNT_VOLUME`. The volume lock remains held during the write transaction and is released by closing the handle on completion or failure. If any volume cannot be locked, previously acquired locks are released, and the operation fails closed. Drive letters are not permanently removed. **Do not assume that all Windows USB bridges or filesystems support this workflow** until they pass live testing.

**Important:** Temporary volume dismount is an I/O-affecting operation. Close applications using the patient drive. Use a separate healthy destination for a persistent region journal. If RAM-only mode is selected, there is no crash recovery of the active region.

## Failure-region boundary checks

Quick and Full scans now record a separate `error_boundary_investigation` object after the primary read pass. For at most eight known failed ranges per round, DriveRepair attempts sector-aligned, read-only probes on **both logical sides** of the failing request, moving outward in bounded steps until it sees repeatable reads or reaches a limit. Default request sizes are up to 64 KiB, with a maximum of 16 additional read operations per scan-stage invocation and a **soft** 12-second scheduling budget.

These probes establish an *observed* boundary, **not** the precise physical damaged sector. Failing a large request can result from a USB bridge, controller, filesystem filter, or the medium. The method does not write anything. Unreadable data is not reconstructed or silently replaced with zeros. It does not treat adjacent logical sectors as adjacent physical NAND pages, SMR bands, or HDD tracks.

The repeated-suspect comparison step is bounded at 12 suspects and is not a guarantee of a hard timeout: Windows may not cancel a single stalled synchronous raw read. The next engineering stage is dedicated asynchronous I/O with independent device timeouts and cancellation tests.

## Verification before public use

- Windows 10 and 11, elevated user; mounted NTFS, exFAT and RAW devices; separate data, recovery, system and BitLocker volumes
- Open-file lock rejection, partial volume inventory, failed dismount, multi-partition rollback and duplicate identity
- USB disconnect/reconnect *during* scan and *during* durable-journal write; crash, power loss and forced termination on disposable disks
- SSD with synthetic read errors, moderate and severe latency; assert bounded probes and report unresolved bytes
- macOS/Linux behavior is **unchanged** by this Windows preparation flag

These platform and physical-write tests **have not been completed in this build**. This is still an experimental engineering version, not certification for a consumer's only copy of their files.
