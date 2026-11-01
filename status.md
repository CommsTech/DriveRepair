# Status — 2026-11-01

PRIVATE TEST — **0.3.3b1** + Windows sparse rescue on Gitea `main`; Seagate 1 TB USB lab measured.

## Merged

| PR | Change |
|----|--------|
| [#86](https://git.commsnet.org/commstech/DriveRepair/pulls/86) | 0.3.3b1 integrity-aware dashboard (`integrity-*`, GUI map, rescue dashboard) |
| [#87](https://git.commsnet.org/commstech/DriveRepair/pulls/87) | Windows `FSCTL_SET_SPARSE` before rescue `ftruncate` so `--max-chunks` works |

## Lab — Seagate ST1000LM048 1 TB

| Field | Value |
|-------|-------|
| Disk | **2** / `windows:PhysicalDrive2` |
| Model | ST1000LM 048-2E7172 |
| Size | 1000204886016 (~931 GiB) |
| Identity | `138b614ad5ea` |
| Outputs | `D:\DriveRepairLab\seagate_st1000lm048_1tb_20261101_151108\` (never on patient) |

| Step | Result |
|------|--------|
| list | OK |
| health | `unknown` (smartctl not installed) |
| monitor | `attention`; preserve-first |
| triage 128 | 0 errors; slow@0 (~156 ms); ~0.014% coverage |
| sample 64 | 0 errors |
| benchmark | **~65.6 MiB/s**; median ~113 ms; p99 ~195 ms |
| integrity offline | single-bit flip → mismatch@1 MiB → restore-copy → **byte-exact** |
| bounded patient rescue | deferred — UAC prompt blocked re-elevation after sparse fix; script ready: `desktop/scripts/run_elevated_seagate_st1000_lab.ps1` |

Honesty: triage/sample prove readability of sampled regions only. Integrity restore needs a trusted reference; it does not invent original bits.

## Tests

- After 0.3.3b1: **176 OK (skipped=11)**
- After sparse fix subset: **26 OK** (recovery + integrity + dashboard)
