# Architecture notes — 0.3.3b12 desktop

1. **Bounded failed-range investigation** — `investigate_failed_ranges` increments the attempt budget **before** each neighbor read so hard I/O cannot overrun the planned probe count.
2. **Cooperative STOP** — `stop_control` + `--cooperative-stop-stdin`: UI may send STOP; honored only at safe phase boundaries (no mid-sector tear-down of exclusive handles).
3. **Progress model** — Qt/guided paths separate phase progress from overall job progress; media rewrite paths respect profile caps (SMR-aware).
4. **Windows write prep** — with `--auto-lock-volumes`, lock then dismount patient volumes before exclusive raw-disk open; abort and release on failure; never force-dismount without lock (0.3.3b11).
5. **Error boundaries** — failed I/O triggers bounded two-sided aligned neighbor reads; read-only; does not authorize writes.
6. **Qt** — Fix goal still passes `--auto-lock-volumes` after confirmations; `IO_TELEMETRY` + `DRIVEREPAIR_GUI_DEBUG` file mirror for Admin lab sessions.
7. **Prior layers** — media profiles (SMR), adaptive scan/checkpoint, surface-map accuracy, native inspect (0.3.3b8–b10) unchanged in role.
