# Status — 2026-11-01

PRIVATE TEST — **0.3.1b1 Last-Resort** + findings `20261101T203616Z` remediated + Samsung PM841 lab.

## Code

- Findings export DriveRepair-only rows remediated (`docs/FINDINGS_REMEDIATION_20261101_203616.md`)
- Health soft-fails to `status=unknown` when `smartctl` missing (no invented pass)
- Windows live rescue + SMB mapped-drive destination isolation on main

## Lab — Samsung PM841 256 GB (drive **E:** / `PhysicalDrive2` / `e5a0dfacc956`)

Metrics under `D:\DriveRepairLab\samsung_pm841_256_20261101\` (never on E:).

| Step | Result |
|------|--------|
| list | OK — USB Get-Disk identity |
| health | smartctl not installed → unknown |
| monitor | attention (SMART unknown); preserve-first |
| triage 128 | 0 errors; ~127 MiB readable; 0.05% coverage |
| sample 64 | 0 errors |
| benchmark | ~165 MiB/s; median latency ~41 ms; p99 ~175 ms |
| rescue multipass | **in progress** on D: (image growing; ~142 GiB+ observed mid-run) |

## Tests

Desktop suite: **159 OK (skipped=11)** after findings pass.
