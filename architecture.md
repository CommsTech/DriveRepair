# Architecture notes — 0.3.3b6 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / `monitor-external` / benchmarks / **`probe-region`** (bounded read-only subdivision; zero patient writes). Scans never rewrite media.
2. **Recover** — `rescue-image`, `carve-image`, `recover-image`, ZIP salvage, FAT32/NTFS/exFAT undelete, TSK optional, `verify-images`.
3. **Integrity (image-only)** — `integrity-baseline` / `integrity-audit` / `integrity-restore-copy`.
4. **Detect** — `detect-filesystems`; unsupported FS → RAW carve path.
5. **Repair clone** — `check-ext-image` / `repair-ext-image` on clones only.
6. **Direct / guided repair** — `guided_repair.py` + `care-external` / `care-image`; RAM or disk journal; error-budget partial outcomes (0.3.3b5).
7. **Maintenance (0.3.3b6)** — `maintenance.py`: read-only `firmware-info`; Windows `optimize-volume` advisory with gated expert `--execute`. No vendor firmware flash from DriveRepair.
8. **In-Place Media Refresh** — Adaptive/Full rolling journal; optional `journal=memory`.
9. **Preferences** — `preferences.py` remembers non-sensitive UI choices only; destructive acks never persisted.
10. **Linux offline system recovery** / **Rescue display** — unchanged roles.

## Soft mechanical indicators

- Latency maps + SMART/NVMe; Windows HealthStatus fallback; scan errors expose native `winerror` when present.
- Read errors / errno=22 alone are not proven media failure or mechanical FAIL.

## Presentation vs recovery

- Engine owns patient I/O; GUI launches CLI only.
- `DRIVEREPAIR_GUI_DEBUG` mirrors UI/engine text to a lab log file and enables faulthandler.
