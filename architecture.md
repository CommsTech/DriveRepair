# Architecture notes — 0.2.0 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / benchmarks (read-only sources).
2. **Recover** — `rescue-image`, carving, ZIP salvage, FAT32 undelete, `verify-images` (writes only new files/dirs).
3. **Repair clone** — `check-ext-image` / `repair-ext-image` clone then optional `e2fsck` on the copy only.
4. **Experimental in-place refresh** — `refresh-image` / `refresh-external` rewrite only fully readable chunks after multi-ack; skipped unread ranges are never invented.

GUI (`gui.py`) drives the same CLI as a subprocess. Packaging: `scripts/build_desktop.py` builds a zipapp `.pyz`; wheel entry points are `driverepair-desktop` and `driverepair-gui`.

Rust under `src/` remains Gate-0 fail-closed historical code, not the desktop recovery engine. Media refresh remains research-only.
