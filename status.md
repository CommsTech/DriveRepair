# Status — 2026-11-01

PRIVATE TEST — **0.3.3b2** journal-safe rescue status on `main` candidate; Seagate 1 TB USB still sacrificial write-verify target.

## Product

- Version `0.3.3b2`: `rescue-status`, exclusive rescue writer lock, journal-authoritative completion
- Lab/PowerShell dock helpers **removed from the repo** — use CLI/GUI only
- Windows fixes retained: sparse EOF, integrity `O_BINARY`, RAW-disk idle for refresh

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2 / `138b614ad5ea`)

| Step | State |
|------|--------|
| Wipe (Clear-Disk) | Done — PartitionStyle **RAW** |
| Full `refresh-external` write+readback | Pending (must run via elevated CLI, not lab scripts) |
| Public release | **Blocked** until sacrificial full-surface verify completes |

Lab evidence (out of tree): `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
