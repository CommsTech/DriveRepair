# In-Place Media Refresh

Dedicated destructive mode **alongside** image-based recovery. It does not replace rescue/imaging and is **not** equivalent to having a backup.

## Rolling journal

Active region state machine:

`SAVED → WRITING → VERIFIED → COMMITTED`

1. Read region with ≥2 identical consistency reads.
2. Persist original bytes to `region.bin` and mark `SAVED`.
3. Mark `WRITING`, rewrite in place, flush.
4. Optional verify read → `VERIFIED`.
5. Advance and clear blob → `COMMITTED`.

On restart, an interrupted `SAVED`/`WRITING` region is restored from the journal (or flagged if the blob is missing/corrupt) before new work continues.

## Modes

| Mode | Behavior |
|---|---|
| `adaptive` (default) | Probe latency; refresh unusually slow but consistently readable regions |
| `full` | Sequential whole-surface refresh (high risk; long on multi-TB USB) |

Unreadable or inconsistent sectors are **never** auto-rewritten.

## Live dashboard

Non-JSON runs show a terminal dashboard (phase, bar, surface map, latency, health indicators).  
`mechanical*` is inferred from extreme latency streaks / I/O patterns — USB docks do not provide acoustic microphones.

`--auto-escalate` (default on) subdivides slow/failed probe zones for deeper testing before refresh.

## Journal backends

| Backend | Region bytes | Meta | Resume strength | Speed |
|---|---|---|---|---|
| `disk` (default; required for hardware) | disk, fsynced + directory-fsynced | disk | Crash-resumable if journal disk survives | Slower |
| `hybrid` (image tests only) | RAM | disk | NOT crash-safe for an in-flight write | Fast |
| `memory` (image tests only) | RAM | disk checkpoint | NOT crash-safe for an in-flight write | Fastest |

`--after-run keep|delete|ask` controls whether the journal directory is removed after a successful run.

## Live hardware gate

External refresh requires `--ack-unvalidated-hardware`. On Windows, an **elevated Administrator** terminal is required for `GENERIC_WRITE` on `\\.\PhysicalDriveN`.

### First Windows USB live adaptive result (2026-11-01)

Patient: Seagate ST12000N ~12 TB via USB dock (`windows:PhysicalDrive2`, fake serial suffix `0001`). Adaptive pass with 128 probes selected 7 slow readable MiB regions; all 7 MiB rewritten and verified; no skips. Interrupt/USB-disconnect fault injection on sacrificial hardware is still outstanding before treating the mode as generally validated.

## Safety hardening — version 0.2.7

- The active-region blob is durably stored before the patient write; metadata is atomically saved and fsynced.
- Any write/read-back error aborts immediately with the blob intact; failures are not mislabeled as skipped untouched sectors.
- Adaptive queue head is not removed until VERIFIED/COMMITTED, preserving recovery work on interruption.
- VERIFIED resume rechecks the region and commits exactly once; WRITING resume restores original bytes and verifies before retrying.
- Image refresh tokens exclude `mtime`, which necessarily changes during successful in-place operations.
- Hardware refresh rejects RAM-only journal backends, disabled readback, macOS raw mode, and unverified journal storage separation.
- Live Linux requires the source to have a serial, no mounted children/holders, and a demonstrably separate journal filesystem. Windows requires a distinct locally mapped journal disk and no drive letters mounted on the patient.
- GUI defaults to disk journaling and requires the user to type the selected device ID before starting.
- Fault-injection tests cover torn writes, failed readback, VERIFY/COMMIT resume, and adaptive queue resume. Physical USB power-loss/disconnect verification is **NOT PROVEN**.
