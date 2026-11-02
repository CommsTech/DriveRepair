# DriveRepair 0.3.3b11 — Mounted-volume preparation and bounded error-boundary review

**Baseline:** `DriveRepair-main(20261102-182724).zip` supplied November 2, 2026.  
**Engineering status:** Experimental, suitable for additional controlled tests only; not a general-public hardware repair release.

## Evidence from the current Windows lab

The supplied SSD screenshots showed a successful read-only sample run advancing to ~94.4% of its planned quick-scan work, reporting ~47.61 GiB read and 20 failed I/O requests before the additional investigation stalled. The debug console reported `Patient has mounted drive letter(s) E; unmount/stop using the filesystem before in-place refresh`. This explains why that particular guided run did not progress into physical writes; it does not establish whether the errors originated in NAND, the USB bridge, host stack, power or cabling. The unrelated Qt font warning does not account for the raw-media refusal.

The previous code contained Windows `FSCTL_LOCK_VOLUME` and `FSCTL_DISMOUNT_VOLUME` support but rejected mounted letters before reaching the locking implementation. It also opened the raw physical disk before locking its partitions. An SSD with many suspect locations could incur excessive additional reads: the repeated-probe stage permitted up to 64 suspects, and the deeper investigation budget was higher than warranted for a degraded device.

## Implemented changes

1. **Explicit temporary volume preparation:** Qt Fix workflow explains the action and, after identity and destructive-operation confirmation, passes `--auto-lock-volumes` to `care-external`. This flag also exists for the advanced `refresh-external` CLI. Neither read-only commands nor image-file operations gain this flag. Drive letters are **not permanently removed**.
2. **Windows lock ordering:** Acquire exclusive locks on each discovered patient filesystem volume *before* opening the raw disk for writes; attempt dismount only after each lock succeeds. If any step fails, close all held handles, do not force dismount, and abort before writing. Folder mount paths, ambiguous volumes and partial partition-inventory failures remain blocked.
3. **Two-sided bounded read-only checks:** A failed request now receives a limited inspection of its immediate logical neighbors, moving outward in aligned windows until repeatable reads are observed or a safety/time/operation budget is exhausted. This is stored separately as `error_boundary_investigation` and does not authorize any source write.
4. **Reduced extra reads:** The quick-scan repeated-suspect stage is limited to 12 suspects with a 15-second *soft* scheduling budget; the full adaptive scan uses a lower retry-call budget and at most eight failed requests per batch. The operating system may still block a single I/O call for longer.
5. **User-facing failure information:** On a busy Windows filesystem, the Qt result panel now recommends closing applications with open files and retrying, rather than presenting only an exit code.
6. **Docs/version:** updated version to `0.3.3b11`, updated desktop and project README/changelog, added `docs/WINDOWS_VOLUME_PREPARATION_AND_ERROR_BOUNDARIES.md`.

## Regression evidence

- Full Python suite: **285 executed, 281 passed, 4 platform-specific skipped** on Linux.
- New synthetic tests: 11, covering both logical sides, disk edge bounds, denied/reconnected-device classification, per-batch budgets, volume-letter gating, GUID prioritization, duplicate/unknown mount rejection, and CLI flag scope.
- `compileall`: passed.
- Portable `.pyz`: built; `--help` and synthetic image triage scan passed.
- Python wheel: built using setuptools.
- Gitea patch: `git apply --check` passed; applying to a clean original ZIP source reproduces all changed files byte-for-byte.
- **Not verified:** PySide6 native GUI clickthrough (not installed), Windows volume locks/dismounts, physical USB-dock write behavior, power-cut recovery, macOS, Linux/macos boot media, native Rust builds.

## Safety and semantics

- A successful Windows exclusive volume lock indicates no other open filesystem files, per Microsoft documentation. A forced dismount without a successful lock is not used: it can disrupt processes and may be remounted automatically by Windows.
- The code does **not** attempt to unmount a system/boot/pagefile volume and continues to use device identity checks. An incomplete or hung Windows inventory is an explicit blocker.
- An error from a 16 MiB request is not evidence that all 16 MiB are physically defective. The added probes find surrounding readable *logical* regions only. They cannot distinguish damaged NAND/platter surfaces from transport errors without further evidence.
- The probe time budget limits **additional scheduled reads**, not a blocked Windows kernel request. Interruptible asynchronous device I/O is future work and must be verified against real hardware.
- Existing scan-then-repair behavior remains: the new code does **not** yet interleave newly authorized write transactions with long-running full scans. Similarly, it does not attempt to reconstruct unreadable bytes or certify SSD/HDD hardware health.

## Next controlled Windows tests

1. Use a **disposable** NTFS/exFAT external USB disk, with no important data. Confirm an open file causes `FSCTL_LOCK_VOLUME` to fail and no writes occur.
2. Close all open handles, redo an explicitly confirmed Fix workflow and verify temporary lock, dismount, write, readback and subsequent mount behavior.
3. Repeat for multiple partitions, GUID-only volumes, BitLocker volumes, disconnected docks, and altered drive numbers; logs should report safe rejection, not inferred success.
4. On a synthetic/fault-injected SSD fixture, measure probe count, true unique coverage, read latency and the two-sided boundary reports. For actual SSDs, watch controller/USB timeout behavior and request-level latency without forcing further in-place writes.
5. Only after these gates, investigate cooperative write cancellation and a durable, verified interrupted-transaction resume loop.

## References

- Microsoft FSCTL_LOCK_VOLUME: https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_lock_volume
- Microsoft FSCTL_DISMOUNT_VOLUME: https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_dismount_volume

**No hardware write was performed by this engineering build or its tests. No Gitea repository was pushed.**
