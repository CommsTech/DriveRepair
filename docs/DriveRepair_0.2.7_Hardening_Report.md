# DriveRepair 0.2.7 — Rolling-journal hardening and release evidence

Date: 2026-11-01  
Baseline: user-uploaded `DriveRepair-main(1).zip`  
Release status: **PRIVATE TEST ONLY — RAW-DRIVE WRITE PATH NOT HARDWARE VALIDATED**

## Executive summary

The supplied source already contained `refresh-image`, `refresh-external`, adaptive and full in-place refresh, and the four-state rolling journal (`SAVED → WRITING → VERIFIED → COMMITTED`). The implementation had dangerous failure paths. This hotfix corrects those paths in source code and tests, but does not certify the physical-drive recovery process.

## Engineering changes

| Risk in baseline | Implemented correction |
|---|---|
| Default `hybrid` journal stored original bytes in RAM during physical writes | `disk` now default, mandatory for `refresh-external`; `region.bin` is fsynced before WRITING |
| Failed write/failed readback could erase original journal and continue | Abort with `aborted_write_or_verify_error`, persist active transaction and original bytes; never treat a partially written region as an untouched skip |
| Adaptive queue item popped before write was safely committed | Peek until VERIFIED and COMMITTED; persist queue update atomically with progress accounting |
| Crash at VERIFIED could skip accounting | Re-read and compare on resume; commit exactly once; COMMITTED recovery does not double-count |
| Torn write during crash could be lost | WRITING recovery restores from journal and verifies before retrying (tested on simulated image) |
| Image refresh token changed mid-run from file mtime | Dedicated stable identity token excluding mutable mtime |
| Incomplete/failed scans could be reported as success | Non-success status for skips, probe I/O errors, failed writes; adaptive probe errors now abort before any rewrite |
| Journal cleanup could occur after some incomplete jobs | Auto-delete journal only after exact `completed` state with no active transaction |
| Journal could be put on the patient | Linux journal ancestry and Windows local drive-letter/physical disk preflight; reject unprovable separation |
| GUI/Windows launcher used RAM journal or automatic deletion | Default to disk journal, retain results, require typed device ID in GUI and PowerShell launcher |
| Windows volume locking covered only drive letters | Discover volume GUID access paths; reject unknown mount paths; require successful volume locks/dismount where identifiable |
| Health dashboard implied media health without data | Default indicators to `UNKNOWN`, not `OK` |
| Inadvertent competitor-name references | Removed from current shipped source/docs |

**Important:** A read-back match proves only that the bytes currently readable through that device/bridge match the journal, not that the medium's physical lifespan was restored. A rolling journal only protects the active region; total-drive failure can still lose all data. Original unreadable regions are skipped, not reconstructed.

## Test evidence (executed in Linux container)

- Baseline: 87 tests ran, with one Windows-only skip.
- Updated: **98 tests ran, 97 passed, 1 Windows-only skip.**
- Additional tests cover torn writes, write failures, readback failures, interrupted adaptive queues, VERIFIED and COMMITTED recovery, stable in-place image identity, and rejection of unsafe live options.
- No real physical disk was opened or written during testing.
- Syntax compilation of desktop Python package: passed.
- Portable `.pyz` smoke: 65,536-byte synthetic patient image successfully rewritten with durable disk journal; readback matched pre-run SHA-256 `6fc179cfd193754e6109ad043f56d146c7e7d7c3623ffceae318266286f58388`.
- `.pyz`, source `.zip` and wheel archive CRC checks: passed.
- Python wheel build for version 0.2.7: passed.
- Patch applies to a clean Git checkout of the supplied archive: passed. `.gitattributes` enforces CRLF for the PowerShell file, so use a normal Git checkout rather than `git apply` inside a loose extracted directory.

## Unverified or incomplete

1. Real USB hot-disconnect, unpowered dock, reset, read-only mount conflicts, USB bridge identifier changes and partial sector writes on actual 12 TB hardware.
2. Windows volume GUID locking and physical-device sector I/O under actual Windows kernel, user permissions and dock firmware.
3. macOS raw media refresh: **disabled** until exclusive locking and safe hardware support are engineered and tested.
4. Rust BIOS/UEFI boot images: not compiled, validated or integrated in this work.
5. Persistent life extension, physical-wear reversal, head/platter damage repair: **not proven and not claimed**.
6. Data recovery from unreadable original sectors (no intact bytes or redundancy): not possible by this rewrite mode; consider specialist recovery before any writes.
7. Independent security review and real-drive failure-mode matrix: not completed.
8. No changes pushed to the user's Gitea server.

## Tested commands for synthetic images only

From the `desktop` directory, using a **disposable regular-file test image**:

```bash
python -m unittest discover -s tests -v
python -m driverepair_desktop --help
python -m driverepair_desktop refresh-image \
  --image /path/to/disposable-regular-file.img \
  --journal /path/to/separate-storage/new-journal \
  --mode full --journal-backend disk --after-run keep \
  --ack-risk --ack-destructive --ack-no-backup --ack-data-loss-risk --json
```

**This example modifies the supplied image. Never point it at valuable data.** Hardware use is not approved by this report. The laptop's internal disk holding the journal should be healthy and have enough free space for region bytes, metadata and safety margin. The new journal directory must not already exist.

## Distribution

- `DriveRepair_0.2.7_Hardened_Source.zip`: source only, excluding cached Rust targets and generated binaries.
- `DriveRepair_0.2.7_Safe_Journal_Hotfix.patch`: standard Git patch from uploaded snapshot.
- `DriveRepair-0.2.7.pyz`: Python 3.10+ portable CLI/GUI; GUI requires Tk.
- `driverepair_desktop-0.2.7-py3-none-any.whl`: installable Python wheel. Not a signed `.exe` or `.app`.

## Required acceptance before physical release

Independent sacrificial drive tests demonstrating all-or-nothing region journaling through forced power losses, unplug/replug, device swap, USB write-cache lies, flush failures, short writes, resumed transaction corruption, destination-journal disk full, OS mounts/locks, and expected SMART and temperature changes. Any incomplete journal must prevent a green-success claim. Until that is complete, do not use this build to refresh irreplaceable data on the 12 TB disk.
