# Architecture notes — 0.2.0 desktop

Desktop workflows in `desktop/driverepair_desktop`:

1. **Diagnose** — `list` / `scan` / `health` / benchmarks (read-only sources).
2. **Recover** — `rescue-image`, carving, ZIP salvage, FAT32 undelete, `verify-images` (writes only new files/dirs).
3. **Repair clone** — `check-ext-image` / `repair-ext-image` clone then optional `e2fsck` on the copy only.
4. **In-Place Media Refresh** — dedicated mode with rolling journal (`meta.json` + `region.bin`), Adaptive/Full strategies, consistency reads, Windows volume lock / Linux `O_EXCL`; does not replace image recovery.

GUI (`gui.py`) drives the same CLI as a subprocess. Packaging: `scripts/build_desktop.py` builds a zipapp `.pyz`; wheel entry points are `driverepair-desktop` and `driverepair-gui`.

Rust under `src/` remains Gate-0 fail-closed historical code, not the desktop recovery engine. Media refresh remains research-only.
