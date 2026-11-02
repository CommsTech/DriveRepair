# Architecture notes — 0.3.3b7 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / `monitor-external` / benchmarks / `probe-region`. Adaptive full scan (`adaptive_scan.py`) varies read size, defers failed extents as UNKNOWN, and never writes during scan.
2. **Recover** — image rescue / carve / undelete / verify paths unchanged.
3. **Integrity (image-only)** — baseline / audit / restore-copy.
4. **Detect / repair clone** — filesystem detect; ext repair on clones only.
5. **Direct / guided repair** — targeted rewrite with RAM or disk journal; bounded batches when candidates exceed budget (0.3.3b7).
6. **Maintenance** — firmware-info (read-only); optimize-volume advisory with gated execute.
7. **Anomaly history** — `scan_history.py` stores only offset/classification metadata under opt-in; never grants writes.
8. **Dependencies** — `dependencies.py` detects optional tools; WinGet smartctl only with explicit approval.
9. **GUI** — staged job selection + **Start job** / **Stop job**; preferences; debug log mirror via `DRIVEREPAIR_GUI_DEBUG`.

## Soft mechanical indicators

- Latency maps + SMART/NVMe; Windows HealthStatus fallback; WinError 1117 classified as I/O device error (cause unproven).
- Read errors alone do not confirm platter failure.
