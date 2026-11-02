**0.3.3b12 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Bounded I/O investigation budgets, cooperative STOP, phase vs overall progress, Qt IO telemetry. Not a public physical-repair release. See `docs/BOUNDED_IO_AND_SAFE_STOP_0.3.3b12.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b12** bounded I/O + cooperative stop + Qt upgrade.

## Product

- Version `0.3.3b12`: investigate_failed_ranges budget increments before read; cooperative STOP at safe boundaries; phase progress vs overall; media rewrite caps; Qt IO_TELEMETRY + Admin `DRIVEREPAIR_GUI_DEBUG` retained
- New `stop_control` module; `--cooperative-stop-stdin` private UI channel
- Prior 0.3.3b11 volume lock/dismount + error-boundary probes retained

## Lab evidence

- Unit: `test_b12_reliability` 5/5 passed
- Sacrificial Seagate ST1000LM048 write+verify still required before public release

## Seagate / USB patients

| Step | State |
|------|--------|
| Bounded I/O + cooperative STOP private validation | Ready |
| Mounted-letter Fix with `--auto-lock-volumes` | Ready for disposable NTFS/exFAT validation |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b12/`
