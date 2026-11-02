# Architecture notes — 0.3.3b11 desktop

1. **Windows write prep** — `media_refresh` / care-external: with `--auto-lock-volumes`, lock each patient volume (`FSCTL_LOCK_VOLUME`) then dismount (`FSCTL_DISMOUNT_VOLUME`) **before** exclusive raw-disk open; abort and release on any failure; never force-dismount without lock.
2. **Error boundaries** — failed I/O triggers bounded two-sided aligned neighbor reads (`error_boundary_investigation`); read-only; does not authorize writes.
3. **Budgets** — quick repeated-suspect stage capped (12 / ~15s soft); full adaptive retries reduced; OS may still block individual I/O longer.
4. **Qt** — Fix goal passes `--auto-lock-volumes` after explicit confirmations; busy FS guidance in results; debug log mirror via `DRIVEREPAIR_GUI_DEBUG`.
5. **Prior layers** — media profiles (SMR), adaptive scan/checkpoint, surface-map accuracy, native inspect (0.3.3b8–b10) unchanged in role.
