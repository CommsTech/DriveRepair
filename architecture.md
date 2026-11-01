# Architecture notes — 0.2.5 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / benchmarks (read-only sources).
2. **Recover** — `rescue-image`, carving, ZIP salvage, FAT32 undelete, `verify-images` (writes only new files/dirs).
3. **Repair clone** — `check-ext-image` / `repair-ext-image` clone then optional `e2fsck` on the copy only.
4. **In-Place Media Refresh** — gated Adaptive/Full with rolling journal; Windows volume lock / Linux `O_EXCL`.

## Presentation vs recovery (90/10)

- Engine owns all patient I/O.
- `progress_events.ProgressEmitter` throttles JSONL (~10 Hz) for GUI consumers (`--progress-jsonl`).
- `refresh_display.RefreshDashboard` paints TTY panels and forwards the same events to the emitter.
- `gui.py` is a dark industrial Recovery Workstation: live sector map, media/transport/mechanical* health, metrics. It only launches CLI subprocesses.
- See `docs/PRESENTATION_LAYER.md` for the Rust UI migration path (same JSONL contract; ARM + x86).

Rust under `src/` remains Gate-0 fail-closed historical code, not the desktop recovery engine. Media refresh is PRIVATE TEST ONLY — no wear-reversal claims.
