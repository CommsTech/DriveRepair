# Status — 2026-11-01

PRIVATE TEST — **0.3.3b3** GUI workflow fix + CI repair in progress; Seagate 1 TB USB still sacrificial write-verify target.

## Product

- Version `0.3.3b3`: Start-here Notebook navigation fix, idle dashboard collapse, portable `.pyz` child engine, Windows live rescue GUI path exposed
- Empty refresh-journal directory no longer blocks a new `--mode full` start
- Lab/PowerShell dock helpers remain **out of tree** — use CLI/GUI only

## CI (Gitea)

- Clippy failed on stable 1.99 `useless_borrows_in_formatting` in `src/ui/menu.rs` (fixed)
- Offline job referenced stale `DriveRepair-0.3.1b1.pyz` (aligned to `0.3.3b3`)
- macOS host runner lacked Node and cancelled Linux matrix jobs — required CI now ubuntu-latest only

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2 / `138b614ad5ea`)

| Step | State |
|------|--------|
| Wipe (Clear-Disk) | Done — PartitionStyle **RAW** |
| Full `refresh-external` write+readback | Pending elevated CLI/GUI (no new UAC available this session) |
| Public release | **Blocked** until sacrificial full-surface verify completes |

Lab evidence (out of tree): `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
