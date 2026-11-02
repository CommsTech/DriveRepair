# Architecture notes — 0.3.3b10 desktop

1. **Qt workstation** — progress % is operation completion (not probe-fraction); surface map (`surface_map.py`) paints only verified byte fractions per cell.
2. **Sampling** — Quick Check/Repair plan >=10% unique LBA coverage with recorded seeds; Full scan adaptive + checkpoint/resume (0.3.3b9).
3. **Rates / ETA** — recent-window throughput vs job average; repair % from transaction queue.
4. **Host inspection** — `windows_native.py` / `host_capabilities.py` / `inspect-storage`: read-only descriptors; never authorize writes.
5. **Media / guided repair** — SMR/CMR/SSD/NVMe profiles (ST1000LM048 = SMR); durable journal option on healthy disk; RAM-only remains non-resumable for writes.
6. **Firmware** — Rust `firmware_inspect` vendor-hint traits only; no flash/VSC/TTL/NVMe unlock paths.
7. **Debug** — `DRIVEREPAIR_GUI_DEBUG` mirrors Qt/Tk engine logs to lab files.
