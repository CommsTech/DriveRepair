# Status — 2026-11-01

PRIVATE TEST — **0.3.3b5** error-aware guided repair applied; Seagate 1 TB USB still sacrificial write-verify release gate.

## Product

- Version `0.3.3b5`: after `aborted_error_limit`, bounded investigation of known failed offsets; partial outcomes (`partial_repair_unresolved_data` / `recovery_required`) instead of global write veto
- Sector-aligned double-read candidates; unreadable/disagreeing regions quarantined; GUI metrics/colors for not-scanned / read / slow / needs investigation / error
- Read errors alone no longer force mechanical FAIL; SMART/disconnect/identity criticals still block writes
- Retains 0.3.3b4 Direct Repair / RAM-only journal; lab helpers remain **out of tree**

## Validation (package report)

- Upstream: 231 tests (228 pass / 3 skip); no physical disk exercised
- Local unit tests run on apply branch before merge

## Seagate ST1000LM048 1 TB (USB / PhysicalDrive2 / `138b614ad5ea`)

| Step | State |
|------|--------|
| Wipe (Clear-Disk) | Done — PartitionStyle **RAW** |
| Elevated Quick/Full repair or refresh-external write+verify | Pending on sacrificial media |
| Public release | **Blocked** until sacrificial full-surface verify completes |

Lab evidence (out of tree): `D:\DriveRepairLab\seagate_st1000lm048_wipe_refresh_20261101\`
Artifacts: `docs/releases/0.3.3b5/`
