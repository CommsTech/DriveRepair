# DriveRepair — November 18 workstation, condition and offline-recovery update

**Status:** Source implementation and synthetic testing complete. Native Windows Qt, USB fault-injection, physical HDD repair, and ISO boot qualification **not performed** in this environment. No public hardware qualification is claimed.

## What the screenshots revealed

1. Progress telemetry is intentionally throttled, but the GUI used to plot only the last read in each emitted notification. Whole-drive map coverage was therefore not comparable to attempted/processed bytes. `ProgressEmitter` now accumulates contiguous successful read spans and failed read spans between emitted notifications; the Qt map consumes all reported spans. If the engine lacks evidence, untested remains dark.
2. The screenshot's SanDisk/USB I/O request near byte 500,099,186,688 remained blocked for hundreds of seconds. The Python synchronous Win32 reader cannot guarantee a timeout, and canceling kernel I/O depends on driver cooperation. On Windows external USB guided scans we now cap read requests at **1 MiB** including calibration. The Qt UI labels pending I/O explicitly; opt-in auto-stop supervises **read-only diagnostic** child processes after three minutes with no result. This is not a hard device timeout and does not reset the drive. For a queued read-only rescue, a 240-second watchdog terminates the child, records an incomplete outcome, and advances to the next drive. An image from a stalled job must be checked, not trusted as complete.
3. A GUIDED REPAIR scan reaching 100% scanning phase is **not** 100% repaired. We renamed the metric CURRENT PHASE and retain a separate staged job estimate. A completed phase may still be awaiting a follow-up request or later repair steps.
4. Windows `WinError 5` is physical-drive access denial. A mounted, inaccessible or RAW volume with no lockable volume handle is not a reason to bypass exclusive-access checks. Windows may require elevation, closing applications, or verified offline operation. Nothing here removes those safety gates.

## New controls

- **Rescue data -> Queue multiple drives for rescue:** select multiple freshly enumerated external sources, or Linux offline whole disks when explicitly enabled. Choose a destination directory on a separate healthy disk, confirm the entire plan, then allow sequential read-only, journaled image rescues. Distinct source fingerprints and output names prevent accidental collisions. The authoritative engine verifies source/destination physical isolation and identity before each image is created. Queue decisions, including child failure and timeouts, are appended to durable local event records in the DriveRepair state directory. `COMPLETE` means the command succeeded; inspect each `.rescue.json` for missing ranges before trusting the contents.
- **Bootable media builder:** exports the original Debian trixie live-ISO builder and desktop Python source into a self-contained ZIP kit. **Build live ISO (Linux)** runs the existing `build_live_iso.sh` only on a prepared Linux root session with live-build/debootstrap installed. Qt dependencies are now included in the live-build package list. The builder never writes physical USB devices. The ISO remains `UNVERIFIED` until BIOS, UEFI, storage enumeration, source no-mount, isolation, and recovery tests pass.
- **Offline Linux rescue:** an explicit checkbox allows `list-all-linux` and `rescue-system` for internal disks after booting a separate trusted recovery environment. The CLI still requires a stable serial, fingerprint, an unmounted source and separate destination. It does not enable unattended in-place repair on internal drives.
- **Condition evidence gauge:** the `reliability_score` module summarizes available ATA SMART raw error indicators, NVMe critical warnings, spare/endurance counters, drive power-on hours, optional observed scan failures, and optional manually documented model-specific service-hour rating. It reports confidence and reasons. Missing SMART data returns **UNKNOWN**, not 100/100. The before/after result records controller health assessment and counter deltas; rewriting readable sectors does not reset lifetime wear.
- **Refined visual hierarchy:** transparent Qt labels remove misleading dark label bars, six styled metrics tiles replace dense text, an enhanced 64x12 evidence map and filled throughput trend improve glanceability, and visible status distinguishes phase completion from job completion.

## What this is NOT

- Not a predictive failure-probability model or official manufacturer certification. NVMe percentage-used is a vendor estimate. HDD AFR/MTBF are fleet statistics and cannot be applied as exact remaining-life predictions. Optional manufacturer service-hour comparisons are operator-provided, not independently checked.
- Not a device-driver fix for hung USB bridges. A single synchronous Windows I/O may remain in kernel indefinitely; process termination may not make the adapter responsive. A Linux live OS with separately tested storage drivers is a follow-on recovery route, not guaranteed repair.
- Not a neural reconstruction engine. DriveRepair has deterministic adaptive reads/retries and guarded region writes, **not** a validated learned model that reconstructs unreadable bytes.
- Not proof that guarded HDD in-place rewrite works on all Windows volumes: RAW partitions, mounted volumes, and missing exclusive access remain explicit blockers.
- Not an automatically created boot USB. The GUI builds/exports an experimental *ISO builder*; it does not flash removable disks or claim that an ISO has booted.

## Validation to hand off to a Windows/hardware-capable agent

1. Install PySide6; inspect 100%, 125%, 150% and 200% scaling in a live GUI. Verify the 64x12 map, gauge, labels, keyboard controls, progress labels and queue dialogs. No native Qt package was installed in the build environment.
2. On a healthy sacrificial USB HDD with a dedicated destination on another physical disk, queue two external rescues. Confirm each source's identity, no source writes, independent unique output images, independently readable rescue journals, sequential processing, and batch events. Unplug the first drive mid-scan and verify failure isolation allows the next job to start.
3. Force Win32 raw-read delays, WinError 5, ACCESS_DENIED, inconsistent sector geometry, PowerShell/Get-Disk discovery timeouts, and USB resets. Verify watcher triggers on the read-only worker only and does not abort a journaled write transaction. Record actual last progress timestamp and adapter recovery behavior.
4. Run guided HDD repair only on sacrificial media with a separate journal. Verify all exclusive lock gates, SMART qualification, explicit consent, postwrite SHA-256 readback and independent reopening. The existing repair beta policy must continue blocking generic SSD/NVMe rewrite.
5. Validate condition index against real smartctl JSON for ATA, USB-SAT, NVMe and drives exposing only coarse Windows health. Test hour-counter changes, raw attribute vendor quirks, missing SMART, score and confidence before/after. **Do not make claims of restored lifespan from a higher score.**
6. Build ISO from the GUI on an isolated Debian VM, verify SHA-256 and El Torito entries, then boot BIOS and UEFI VMs, then separate real hardware with NVMe/SATA/USB. Confirm source stays unmounted/read-only until operator explicitly chooses rescue, and a destination is a different physical medium.
7. Run the same tests on 4Kn drives, USB enclosures, SMR HDDs, thin-provisioned destinations and NTFS/RAW cases, and verify diagnostic copy is understandable to both consumer and expert users.

## Tested locally

- `PYTHONPATH=desktop pytest -q desktop/tests`: **360 passed, 11 skipped; 19 subtests passed.** The skipped tests include Qt and other environment-dependent features.
- `python -m compileall -q desktop/driverepair_desktop`: passed.
- Buildable source and patch provided separately; **Cargo, native Windows raw-disk I/O, real HDD SMART/postwrite verification and full ISO boot were not validated here**.
