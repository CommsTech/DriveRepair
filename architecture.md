# Architecture notes — 0.3.3b8 desktop

1. **Diagnose** — list/scan/health/probe; adaptive scan grows/shrinks reads; unique sampled addresses tracked separately from re-probes.
2. **Media profiles** — `media_profiles.py` maps exact known SMR models (e.g. ST1000LM048), confirmed CMR, SSD/HDD/NVMe, or unknown. USB is a bus, not a recording technology.
3. **Guided repair** — Quick: stratified random sample >=10% unique LBA coverage (seed recorded). Full: read-only transfer calibration then adaptive surface pass. Repair writes use <=1 MiB extents; optional CMR left/right neighbor rewrite only under explicit advanced flags (blocked for SMR/SSD/NVMe/unknown).
4. **Identity** — Windows re-ID prefers bounded single-disk `Get-Disk -Number N`; GUI inventory never authorizes writes.
5. **Maintenance / preferences / anomaly history / dependencies** — as in 0.3.3b6–b7.
6. **GUI** — simplified workflow, medium/profile display, staged Start/Stop job; `DRIVEREPAIR_GUI_DEBUG` log mirror.
