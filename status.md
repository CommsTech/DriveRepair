# Status — 2026-11-02

PRIVATE TEST — **0.3.3b6** maintenance/firmware + read-error probe applied; Seagate 1 TB USB still sacrificial write-verify release gate.

## Product

- Version `0.3.3b6`: read-only `probe-region`, `firmware-info`, Windows `optimize-volume` advisory (execute gated); GUI preference persistence (non-sensitive); clearer scan `winerror` / errno=22 reporting
- Retains 0.3.3b4–b5 Direct Repair / error-aware partial outcomes; lab helpers remain **out of tree**
- Admin GUI debug tracking via `DRIVEREPAIR_GUI_DEBUG=1` (file mirror under lab folder)

## Current Seagate evidence (user Windows runs)

- Quick Repair: ~0.0138% coverage; refreshed/verified ~1.8 MiB at two end regions
- Full Scan: many slow 4 MiB ranges; stopped at offset `77561069568` (`OSError errno=22`) ~7.75% — treat as unproven media failure pending bounded probe
- Recommended next: read-only `probe-region` at that offset (no rewrite/zero)

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2)

| Step | State |
|------|--------|
| Wipe (Clear-Disk) | Done — PartitionStyle **RAW** earlier; re-check after recent repair runs |
| Elevated full-surface verify | Still release gate |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b6/`
