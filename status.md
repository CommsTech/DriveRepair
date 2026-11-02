# Status — 2026-11-01

PRIVATE TEST — **0.3.3b4** Direct Repair / RAM-only journal applied; Seagate 1 TB USB still sacrificial write-verify release gate.

## Product

- Version `0.3.3b4`: Diagnose/Rescue **Quick repair** and **Full repair** with **Volatile RAM only** or disk journal; no second-drive image required for targeted refresh
- In-place refresh supports `journal=memory` (non-resumable; torn-write rollback while process lives)
- Scans remain diagnose-only; Windows HealthStatus fallback when SMART/`smartctl` missing
- Lab/PowerShell dock helpers remain **out of tree** — use CLI/GUI only

## Validation (package report)

- Synthetic/mocked paths only in upstream package tests; physical disk not certified
- Local: `test_ram_only_repair` 8/8, `test_guided_repair` 14/14, `test_health` 6/6 PASS

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2 / `138b614ad5ea`)

| Step | State |
|------|--------|
| Wipe (Clear-Disk) | Done — PartitionStyle **RAW** |
| Full `refresh-external` / Direct Repair write+verify | Pending elevated GUI/CLI on sacrificial media |
| Public release | **Blocked** until sacrificial full-surface verify completes |

Lab evidence (out of tree): `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b4/`, `dist/DriveRepair-0.3.3b4.pyz`
