# Issues — 2026-11-01 (0.3.3b3)

## Fixed this cycle
- GUI Start-here buttons selected wrong Notebook children (TclError swallowed) — fixed in 0.3.3b3
- Empty refresh journal directory blocked new runs — `prepare_new` allows empty dirs
- CI Clippy failed on rustc 1.99 `useless_borrows_in_formatting` in `src/ui/menu.rs`
- CI offline package check still pointed at `DriveRepair-0.3.1b1.pyz`
- macOS host runner (no Node) failed early and cancelled Linux matrix jobs — required CI is ubuntu-only

## Open / blocked
- Seagate ST1000LM048 full `refresh-external --mode full` write+verify still required before public release
- Physical Windows GUI USB rescue/refresh not fully qualified
- Optional Windows/macOS CI runners deferred until Node-capable hosts exist
