# Architecture notes — 0.3.3b9 desktop

1. **Diagnose / adaptive scan** — grow/shrink reads; unique vs re-probe accounting; WinError 1117 vs 433.
2. **Scan checkpoint / resume** — `scan_checkpoint.py`: offsets-only local metadata; resume verifies hashed identity/geometry/offset; never stores sector bytes or authorizes writes.
3. **Rates** — `rates.py` recent-window throughput; average retained separately.
4. **Media profiles / guided repair** — SMR/CMR/SSD/NVMe-aware (0.3.3b8); Quick ≥10% stratified coverage.
5. **GUI** — `qtgui.py` (PySide6, optional) preferred by `gui`; Tk remains `gui-legacy`. CLI remains authoritative for identity and writes. `DRIVEREPAIR_GUI_DEBUG` mirrors diagnostics to lab log.
6. **Maintenance / preferences / dependencies** — as in 0.3.3b6–b7.
