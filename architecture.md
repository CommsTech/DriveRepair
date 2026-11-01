# Architecture notes — 0.3.0b1 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / `monitor-external` / benchmarks (read-only).
2. **Recover** — `rescue-image`, `carve-image`, `recover-image`, ZIP salvage, FAT32/NTFS/exFAT undelete, TSK optional, `verify-images`.
3. **Detect** — `detect-filesystems` (FAT/NTFS/exFAT/ext/Btrfs/ZFS/APFS); unsupported FS → RAW carve path.
4. **Repair clone** — `check-ext-image` / `repair-ext-image` on clones only.
5. **In-Place Media Refresh** — Adaptive/Full rolling journal; optional soft sensors (`sensors.SensorSuite`).

## Soft mechanical indicators

- **Primary:** latency maps + SMART/NVMe counters.
- **Acoustic WATCH:** optional mic energy vs baseline (needs `sounddevice`); room noise is not wear proof.
- **Shock STOP:** optional chassis IMU (WinRT accelerometer or injected reader); not platter wobble.
- **SMART deltas:** rising realloc/pending/CRC/NVMe error counters → WATCH during a job.
- Events correlate to the active byte offset when available; never claimed as flying-height metrology.

## Presentation vs recovery

- Engine owns patient I/O; GUI launches CLI only.
- `ProgressEmitter` / `RefreshDashboard` for live UI; mechanical* remains latency-primary with soft overlays.
