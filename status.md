**0.3.3b7 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Adaptive read-only full scans, partial guided maintenance and staged desktop GUI were updated. Native Windows USB hardware writes, Rust builds, BIOS/UEFI boot validation and third-party beta penetration testing remain open. See `docs/ADAPTIVE_SCANNING_AND_SETUP.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b7** adaptive scan + staged Start job UX; Seagate 1 TB USB still sacrificial write-verify release gate.

## Product

- Version `0.3.3b7`: adaptive full scan (grow/shrink reads, defer unreadable as UNKNOWN), WinError 1117 classification, bounded repair batches, optional anomaly history, staged **Start job** / **Stop job**, prerequisite preflight (explicit WinGet smartctl only)
- Retains 0.3.3b4–b6 Direct Repair / error-aware / probe-region / firmware advisory
- Admin GUI debug tracking via `DRIVEREPAIR_GUI_DEBUG=1`

## Current Seagate evidence (user Windows runs)

- Quick Repair: ~0.0138% coverage; refreshed/verified ~1.8 MiB at two end regions
- Full Scan (pre-adaptive): stopped at offset `77561069568` (~errno=22 / possible WinError 1117) ~7.75% — re-test with adaptive Full scan + optional `probe-region`
- Do **not** start jobs until clicking **Start job**

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2)

| Step | State |
|------|--------|
| Wipe / prior repair runs | Lab evidence under DriveRepairLab |
| Adaptive full scan + elevated verify | Pending controlled hardware validation |
| Public release | **Blocked** |

Lab: `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b7/`
