**0.3.3b8 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Media-aware profiles (SMR/CMR/SSD/NVMe), >=10% stratified Quick Repair coverage, bounded Get-Disk identity recheck. Physical write qualification and public beta remain open. See `docs/MEDIA_AWARE_SCANNING_0.3.3b8.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b8** media-aware scanning/repair; Seagate ST1000LM048 treated as **SMR** (datasheet).

## Product

- Version `0.3.3b8`: media profiles; Quick Repair >=10% unique address coverage with recorded seed; Full Repair read-only transfer calibration + adaptive scan; <=1 MiB targeted write extents; optional CMR neighbor rewrite only with explicit `--recording cmr --rewrite-neighbors`
- Windows identity: bounded `Get-Disk -Number N` first; fail closed / `repair_blocked_identity_recheck` if revalidation fails
- ST1000LM048: neighbor rewrites disabled (SMR); do not equate refresh with platter smoothing
- Admin GUI debug tracking via `DRIVEREPAIR_GUI_DEBUG=1`

## Seagate ST1000LM048 1 TB (USB)

| Step | State |
|------|--------|
| Media class | **SMR** (manufacturer datasheet) |
| Discovery timeouts / WinError 1117 | Observed; transport vs media unproven |
| Elevated full-surface verify | Still release gate |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b8/`
