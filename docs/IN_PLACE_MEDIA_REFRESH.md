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

## Offline system disk: last-resort volatile RAM journal (0.3.1b1 follow-up)

`refresh-system` provides an opt-in route for a computer with only one internal
hard drive, after booting a **separate trusted Linux live USB**. This is not an
active-OS repair command and does not create a full backup. The patient is
required to be unmounted, without active holders, and is selected from the
separate `list-all-linux` inventory with an exact 12-character fingerprint.

For a no-second-storage use case, a RAM-backed (`tmpfs`) journal protects **only
the current region**; its metadata and bytes remain in RAM. Default chunk size
is 1 MiB. Each region is read consistently, stored, rewritten and verified
before moving on. The saved data can survive an application crash as long as
the **same live OS and RAM filesystem remain running**, but cannot survive a
host restart, RAM corruption or external-device failure. The UPS/battery check
is a risk-reduction measure, not a durability guarantee. USB docks also need
independent protected power. Full-disk rewrite is not a default or advised
response to possible hardware failure.

The mode stays `EXPERIMENTAL` / `NOT APPROVED FOR VALUABLE MEDIA`. It must never
be advertised as lost-file recovery, a proven rejuvenation treatment, or a
verified filesystem repair. See `ONE_DRIVE_RECOVERY.md` for an example and
preconditions.
