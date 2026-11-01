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

## Live hardware gate

External refresh requires `--ack-unvalidated-hardware`. On Windows, an **elevated Administrator** terminal is required for `GENERIC_WRITE` on `\\.\PhysicalDriveN`.

### First Windows USB live adaptive result (2026-11-01)

Patient: Seagate ST12000N ~12 TB via USB dock (`windows:PhysicalDrive2`, fake serial suffix `0001`). Adaptive pass with 128 probes selected 7 slow readable MiB regions; all 7 MiB rewritten and verified; no skips. Interrupt/USB-disconnect fault injection on sacrificial hardware is still outstanding before treating the mode as generally validated.
