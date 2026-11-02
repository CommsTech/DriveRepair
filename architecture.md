# Architecture notes — 0.3.3b4 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / `monitor-external` / benchmarks (read-only). Scans never rewrite media.
2. **Recover** — `rescue-image`, `carve-image`, `recover-image`, ZIP salvage, FAT32/NTFS/exFAT undelete, TSK optional, `verify-images`.
3. **Integrity (image-only)** — `integrity-baseline` / `integrity-audit` / `integrity-restore-copy` (`integrity.py`): SHA-256 chunk manifests; outcomes are matched / differs / unknown / unreadable. Restore writes a **new** image from a verified independent reference of the same snapshot; does not invent original bits without redundancy.
4. **Detect** — `detect-filesystems` (FAT/NTFS/exFAT/ext/Btrfs/ZFS/APFS); unsupported FS → RAW carve path.
5. **Repair clone** — `check-ext-image` / `repair-ext-image` on clones only.
6. **Direct / guided repair (0.3.3b4)** — `guided_repair.py` + `care-external` / `care-image`: triage or full scan, then targeted rewrite/verify of slow-but-readable regions only. Temporary region storage: process RAM (no journal files, non-resumable) or disk journal (crash-recoverable). Does not invent missing file bytes or fix filesystem metadata.
7. **In-Place Media Refresh** — Adaptive/Full rolling journal (`media_refresh.py`); `journal=memory` holds one active region in process RAM only. Optional soft sensors (`sensors.SensorSuite`).
8. **Linux offline system recovery** — `list-all-linux` / `plan-system-recovery` / `rescue-system` for unmounted internal disks imaged to a separate healthy destination (local, NFS/CIFS/SSHFS). Ordinary `list` still excludes internals.
9. **Rescue display** — `rescue_display.py` + GUI dashboard: committed bytes, gaps, ETA, activity map (not a health/crypto map).

## Soft mechanical indicators

- **Primary:** latency maps + SMART/NVMe counters; Windows HealthStatus fallback when `smartctl` missing.
- **Acoustic WATCH / shock STOP / SMART deltas:** optional soft chassis signals; not platter metrology.
- First SMART observation of nonzero media/pending counters alerts immediately (no silent clean baseline).

## Presentation vs recovery

- Engine owns patient I/O; GUI launches CLI only.
- Offline recovery GUI panel is Linux-oriented; ISO live-build recipes exist but are unboot-tested.
- RAM-only mode: DriveRepair writes no image/journal files; OS paging/hibernation may still touch disk.
