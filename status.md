# Status — 2026-11-01

PRIVATE TEST ONLY — **0.2.7** rolling-journal safety hotfix.

## Hardening

- Default/required journal for live media: **disk** (fsynced `region.bin`)
- Write/readback failure aborts and **keeps** the active transaction journal
- Adaptive queue peeks until COMMITTED; VERIFIED/COMMITTED resume is exact-once
- Health indicators default to `UNKNOWN`
- Auto-delete journal only after exact `completed` with no active transaction

See `docs/DriveRepair_0.2.7_Hardening_Report.md`.

## Live USB lab (PhysicalDrive2 ST12000N, 2026-11-01)

| Test | Result |
|---|---|
| Unit suite | **98 passed** |
| `list` | OK |
| Sample scan 24 chunks | OK — 24/24 readable, 0 errors (~10.5 s) |
| Adaptive refresh 64 probes, `--journal-backend disk` on `D:` | **completed** (exit 0); journal retained |
| Live hybrid journal rejected | OK — exit 1 as required |

Still unproven: USB hot-unplug / power-loss fault injection.
