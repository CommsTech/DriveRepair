# Status — 2026-11-01

PRIVATE TEST — **0.3.3b1 Integrity / Dashboard** applied; Seagate 1 TB USB lab starting.

## Code

- `feature/0.3.3b1-dashboard-integrity` from patch `DriveRepair_0.3.3b1_Dashboard_Integrity.patch`
- Integrity: `integrity-baseline` / `integrity-audit` / `integrity-restore-copy` + GUI map
- Recovery dashboard (0.3.2b1) included: throttled JSONL progress, Resume / Retry gaps
- Prior remediations retained on main (USB fingerprint without location flap; live rescue throttle)

## Lab — Seagate ST1000LM048 1 TB (USB dock)

| Field | Value |
|-------|-------|
| Disk | **2** |
| Model | ST1000LM 048-2E7172 |
| Size | 1000204886016 (~931 GiB) |
| Bus | USB |
| Status | Online |

Outputs go under `D:\DriveRepairLab\seagate_st1000lm048_1tb_*` — never on the patient.

## Lab — Samsung PM841 256 GB (prior)

Paused / superseded by Seagate swap. Metrics under `D:\DriveRepairLab\samsung_pm841_256_20261101\`.

## Tests

Desktop suite pending after apply (target: 175 passed · 1 Windows skip per engineering package).
