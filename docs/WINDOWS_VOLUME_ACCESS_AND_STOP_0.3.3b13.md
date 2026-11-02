# DriveRepair 0.3.3b13 — Windows volume access and read-only Stop

**Experimental. Do not use this build to repair an irreplaceable drive.** All automated tests use synthetic images and mocked hardware interfaces. Windows Qt, dock disconnections, and write/lock recovery remain unqualified.

## What the SSD logs prove

The user-supplied scan attempted ~50 GB of distributed 8 MiB requests, accumulating 14 read errors, then entered bounded investigation. The guided rewrite was blocked by `Unrecognized partition without an accessible volume handle`. It was NOT evidence that a repair ran. Killing a read-only worker after Windows blocked I/O is not evidence of a completed or safely cancelled kernel request.

## Changes

- All Windows partitions reported by `Get-Partition` must have a recognized lockable GUID or volume-letter handle. A partition with empty or null `AccessPaths` is **not** considered equivalent to an unpartitioned disk. RAW, reserved, encrypted, recovery and bridge-hidden partitions fail closed. This may make formerly permitted operations unavailable by design.
- The volume-lock diagnostic identifies the partition number/type where exposed by Windows, and instructs users to choose read-only rescue or a validated offline environment instead of bypassing a missing lock.
- Guided scan results and the targeted repair plan survive a failed pre-write identity or volume-lock validation. Structured result: `repair_blocked_prewrite_access`, `writes_performed=false`.
- Read-only `scan` and `scan-image` now accept `--cooperative-stop-stdin`. A local Qt operator sends `STOP` on stdin. It is honored after the active read returns, and a structured incomplete result is emitted. A stuck Windows kernel call still cannot be interrupted with a Python time limit.
- Qt waits for the cooperative STOP before escalating to read-only process termination; it reports forced exit as an **unknown** last I/O result, never as finished disk repair.
- Dedicated regression tests verify the no-lock and stop-report invariants.

## Your next Windows USB test

1. On a disposable drive, run a **read-only** quick scan, then click Stop. Confirm the result says `stopped_by_user` or explicitly describes forced termination and incomplete coverage.
2. For an external drive with multiple partitions, verify the drive details including partition numbers/types and that a RAW/unknown inaccessible partition prevents write authorization. Do not edit the partition table to get past the check if any data matters.
3. For a disposable, NTFS-formatted external drive with an accessible volume letter, close all applications using it and test the exclusive-lock path only with known-restorable data. Preserve the scan logs.
4. The Seagate/SSD read errors warrant separate USB dock, cable and power testing. The scan's read-error count is not proof of a particular NAND or magnetic defect.

**Out of scope:** controller-level I/O cancellation, RAW partition write bypass, vendor firmware modification, automatic resurrection of failed NAND or mechanical media, and hardware-certified repair.
