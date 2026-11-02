**0.3.3b11 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Explicit Windows volume lock/dismount preparation and bounded two-sided error-boundary probes. Not a public physical-repair release. See `docs/WINDOWS_VOLUME_PREPARATION_AND_ERROR_BOUNDARIES.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b11** mounted-volume preparation + SSD error-boundary budgets.

## Product

- Version `0.3.3b11`: Qt Fix / `care-external` `--auto-lock-volumes` (temp lock then dismount; no force without lock; letters not permanently removed)
- Lock volumes **before** opening raw disk for writes; fail closed on folder mounts / ambiguous inventory
- Two-sided read-only `error_boundary_investigation`; reduced quick-scan suspect/retry budgets
- Clearer Qt busy-filesystem messaging; Admin `DRIVEREPAIR_GUI_DEBUG` retained

## Lab evidence (user SSD)

- Quick sample ~94.4% planned work / ~47.61 GiB / 20 I/O fails; stalled on mounted letter **E:** (expected refusal until auto-lock Fix path)
- Errors unproven (NAND vs USB/host/power)

## Seagate / USB patients

| Step | State |
|------|--------|
| Mounted-letter Fix with `--auto-lock-volumes` | Ready for disposable NTFS/exFAT validation |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b11/`
