# Status — 2026-11-01

PRIVATE TEST ONLY. First Windows live Adaptive Refresh on USB Seagate 12 TB (`windows:PhysicalDrive2`).

## Live lab results

| Pass | Samples | Targets | Rewritten / verified | Elapsed | Result |
|---|---:|---:|---|---:|---|
| 1 (elevated) | 64 | (pre-telemetry) | 2 MiB / 2 MiB | ~45 s | completed |
| 2 (elevated) | 128 | 7 | 7 MiB / 7 MiB | ~136 s | completed, 0 skips |

- Non-elevated open failed with WinError 5 → fixed actionable `PermissionError` (Administrator required).
- Adaptive probe telemetry now reported in JSON (`adaptive_targets`, median/threshold).
- Rolling journal on host SSD under `.agent-temp/`; patient partitions remain unmounted.
- Not a full-surface refresh; not a backup substitute; SMART still unavailable without smartctl/bridge support.
