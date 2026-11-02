# DriveRepair 0.3.3b13 — Windows partition-lock and scan cancellation audit

**Status:** Experimental engineering build. Do not use for unrestricted physical-drive repairs or irreplaceable files.

## Evidence in the user's November 2, 2026 SSD test

The supplied Windows logs show distributed read-only scan requests (typically 8 MiB) across a roughly 500 GB SanDisk USB-attached drive, progressing to around 50.45 billion attempted bytes. The logs record 14 failed read requests before entering the bounded investigation phase. These are failed requests, not proven bad physical sectors. The GUI showed 100% of the *scanning phase*, approximately 75% estimated whole-job progress, and roughly 2.14% unique device bytes read successfully. Those figures are different measures, not contradictions.

After investigation, the old process reported `Unrecognized partition without an accessible volume handle`. That is a **Windows volume-lock/access problem** in the write-preflight path, not evidence that repairs were performed. A separate read-only scan reported the process did not terminate promptly and required a forced child exit after five seconds. Forced process exit leaves its last pending kernel I/O outcome unknown.

## Changes

1. **Fail-closed volume locking:** Every enumerated partition needs a recognized Windows volume GUID or letter handle, even if its access paths are empty. An unpartitioned disk and a partition with no accessible handle are no longer conflated. An unreadable/RAW/recovery/hidden partition is not silently bypassed.
2. **More useful error:** Volume preflight includes Windows partition number and type when available. Repair remains unavailable if Windows cannot lock all required volumes.
3. **Preserved scan findings:** If the pre-write identity/volume-opening step fails, the guided workflow returns `repair_blocked_prewrite_access`, `writes_performed=false`, its entire scan report, and a repair plan rather than dropping evidence in a generic exception.
4. **Cooperative read-only Stop:** `scan` / `scan-image` accept `--cooperative-stop-stdin`. Qt sends STOP via stdin; the engine checks at a completed read boundary and emits `stopped_by_user`, `scan_incomplete=true`, `writes_performed=false`. It cannot interrupt a Windows kernel request already in progress.
5. **Escalation messaging:** If a read-only job does not honor STOP within eight seconds, Qt requests normal termination; if it remains blocked, six seconds later it forces the *read-only child* to exit. That result is never presented as completed scanning or confirmed patient recovery.
6. **Qt status:** The GUI distinguishes a Windows pre-write volume blocker from a disconnected drive. It displays preserved readable bytes/read errors where a scan report is returned.

## Validation performed

- `pytest -q desktop/tests`: **294 passed, 11 skipped**, plus three successful unittest subtests. The warning was a pre-existing test collection issue for a utility class with a constructor.
- Packaged PYZ and installable wheel built successfully from the revised source.
- Real packaged CLI synthetic test: fed `STOP` to a 64 MiB image scan, receiving exit code 3 and structured `stopped_by_user` result with `writes_performed=false` and incomplete coverage.
- New regression tests: inaccessible Windows partition with `[]`, `[null]`, or empty access path; truly unpartitioned disk; scan CLI stop option and partial-report handling.
- Git patch applied to a fresh filtered copy of the exact uploaded `DriveRepair-main (1)(1).zip` baseline; changed files checked byte-for-byte.

## Unverified and open risks

**No native Windows/PySide6 clickthrough or physical USB disk write, dismount, power-failure, firmware or raw partition recovery testing was performed in this environment.** The Windows storage driver may hold a synchronous I/O request for an unbounded interval. Operating-system native cancellation would require a separately tested asynchronous I/O design; a Python timer does not provide one.

A partition with no Windows volume handle now blocks in-place repair (even after a scan). This preserves exclusivity but is intentionally restrictive, and may require a validated offline recovery environment. This update does **not** make unknown/RAW partitions writable through unsafe bypasses. It does **not** provide a new filesystem repair algorithm or sector reallocation capability.

## Recommended disposable hardware validation

1. Select **Check drive** (read-only), initiate a sample scan, press Stop during a normal read, and record exit/status. Re-run with a controlled dock disconnect on a sacrificial drive; verify that no data is written and that an interrupted scan remains incomplete.
2. On a disposable external disk containing an ordinary mounted NTFS volume, verify that exclusive lock/dismount requires confirmation and closes safely when a file is in use.
3. On a disposable disk with a RAW or reserved/unrecognized partition, confirm DriveRepair produces `repair_blocked_prewrite_access` and preserves scan findings without issuing a write.
4. Compare a read-only run through a different USB cable/dock/port or direct SATA for possible transport errors before concluding that NAND or magnetic media is damaged.
5. Preserve USB topology, SMART attributes (when exposed), Windows Event Viewer storage errors, scan checkpoint, and DriveRepair event logs, but redact serial numbers before publishing.
