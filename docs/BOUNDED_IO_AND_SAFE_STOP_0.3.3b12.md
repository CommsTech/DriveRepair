# DriveRepair 0.3.3b12 — bounded I/O, guided Stop and media-aware engineering notes

## Purpose and scope

This cycle fixes a dangerous *software* retry-bound defect found during real
Windows USB-dock testing and makes the graphical UI more informative. It does
not establish the reliability of a physically failing drive, reconstruct lost
bytes, or prove a drive is fit to store valuable data.

## What the user sees

1. Choose the drive. The advisory media profile shows what is known and what
   remains unknown. An external USB bridge may hide the true recording medium.
2. Select **Fix**, **Recover**, or **Check**; do not confuse a scan with a repair.
3. Start the job only after reading the risk/identity confirmations.
4. The **current phase** and **estimated total workflow** use different bars.
   Guided Fix runs through scan, optional investigation and conditional repair.
   The overall percentage is a *phase-weighted estimate*, not a guarantee that
   all LBAs were tested, nor that any sector was repaired. At any point there
   may be zero qualified rewrite candidates.
5. Investigation reports a maximum number of read attempts. Debug mode records
   the current byte offset/size, successful and failed reads, elapsed time and
   the last reported operating state. `Waiting on drive` means a blocked read
   is possible, **not** that DriveRepair is making forward progress.

## Why a scan stalled at 8.4%

In b11, an error-path within bounded bisection only incremented the retry count
on successful reads. A failed 4 MiB read could therefore recursively split
into numerous smaller *failed* requests without exhausting `max_reads`.
This revision charges each attempted read before calling the OS. It also
records elapsed time and emits diagnostic events before requesting a read.
Its wall-clock limit is soft: Windows' synchronous disk I/O may remain blocked
inside a USB driver or disk firmware longer than the configured budget.

## How Stop works

- **Guided Fix scan/investigation:** pressing Stop sends `STOP` to the child
  process through its existing standard-input channel. The engine checks for
  cancellation between read operations; it doesn't close an in-flight OS I/O.
- **Guided in-place rewrite:** Stop is recognized *between committed journal
  transactions*, never while `SAVED` or `WRITING` is active. The output is
  `repair_stopped_safely`; completed/reverified work is still reported.
- **Standalone read-only scan:** the Qt UI can terminate the child, then kill
  it after a grace period if it doesn't respond. This does not make a blocked
  kernel read safely cancellable or prove the USB adapter is working.
- **Crash/power loss during volatile RAM-only writes:** the active original
  bytes may disappear. There is no replayable journal, even with a UPS.
- **Disk-backed journal:** choose storage on a *separate* healthy device and
  preserve the journal until status/transaction integrity is confirmed.

If Windows becomes unresponsive, do not assume that repeatedly pressing Stop
will end a low-level I/O operation. Avoid unplugging during any possible write.

## SMR, CMR, SSD and NVMe handling

| Profile | Investigation | Guided logical rewrite limit | Risk notes |
|---|---|---|---|
| Manufacturer-confirmed SMR | Read-only staged and bounded; no inferred physical zone map | 256 KiB per transaction, max 16 transactions | Avoid neighboring writes and uncontrolled random rewriting; internal shingled-band mapping unknown |
| Independently confirmed CMR | Staged and bounded | 1 MiB per transaction by default; expert-verified neighbors separately gated | Logical adjacency does not guarantee adjacent physical defects |
| Reported SATA SSD or NVMe | Staged and bounded; check health/controller information | 128 KiB per transaction, max 16 | Rewrites consume flash endurance; slow requests do not prove bad NAND |
| Unknown/USB bridge | Read-only evidence preferred until medium established | General bounded fallback, not medium-specific proof | USB connection isn't a recording technology |

The caps constrain potential impact, not physical erase-block alignment. Disk
firmware handles physical remapping and wear leveling. No vendor-specific
service-area editing or flash controller commands are enabled.

## Windows USB and identity prerequisites

`Get-Disk`, CIM and WMIC timed out during the supplied tests. This may indicate
an unresponsive USB bridge, device, storage stack or Windows service. The native
read-only storage inspector offers some information without `Get-Disk`, but it
**cannot authorize raw writes**. DriveRepair must positively identify the
selected disk, verify it is not a system/boot drive, ensure mounted volumes
are exclusively locked, and reconfirm identity before mutation. If any proof
is missing, writes stay blocked. Reconnecting may change `PhysicalDriveN`.

## Hardware acceptance plan (disposable disks only)

- Exercise several separate models through the USB dock, including known SMR,
  known CMR, SATA SSD and NVMe bridge, recording model, serial, transport,
  sector geometry and controller SMART visibility.
- Inject predictable failing reads on synthetic readers and confirm the maximum
  read count. Validate GUI diagnostic offset, pass, phase and job progress.
- On sacrificial hardware, verify safe Stop during scanning and between rewrite
  transactions. Test after unmount, locked file, USB reset, loss of power and
  process termination. Confirm zero unverified write to a different disk.
- Verify source immutability for all read-only modes, resumed scan identity,
  journal durability, and byte-for-byte validation of copied images.
- Compare recovered data correctness, wall time, unique coverage and additional
  I/O, not merely the highest sequential throughput.

**Not tested here:** native PySide6 interaction on Windows, Win32 storage
cancellation, firmware writes, Rust compilation or actual sector repairs.
