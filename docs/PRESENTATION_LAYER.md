# Presentation layer (10%) vs recovery engine (90%)

DriveRepair keeps disk I/O in the recovery engine. CLI and GUI are thin presentation consumers.

## Design rules

1. **Recovery first** — never open patient devices from the GUI process; spawn the CLI.
2. **Low overhead** — progress emits at most ~10 Hz (`ProgressEmitter`, `--progress-jsonl`).
3. **Accurate** — dashboard/map/health reflect engine events; mechanical* is a latency/error proxy (USB docks have no acoustic mic).
4. **Modern, industrial** — dark workstation UI (Tk today); not DOS/blue SpinRite aesthetics.
5. **Cross-platform** — Windows / Linux / macOS; ARM and x86 via Python desktop now, Rust presentation later.

## Current stack

| Layer | Role |
|---|---|
| `media_refresh.py` / scanners / rescue | Recovery engine |
| `progress_events.py` | Throttled JSONL progress protocol |
| `refresh_display.py` | Terminal dashboard + emitter hook |
| `gui.py` | Tk Recovery Workstation (map, health, metrics) |
| `src/` Rust | Gate-0 boot / fail-closed; not the desktop engine yet |

## Rust presentation path (planned)

Keep the same JSONL progress contract so a future `egui` / `iced` / native shell can replace Tk without changing the engine:

1. CLI remains the recovery process (`--progress-jsonl` on stderr; final result JSON on stdout).
2. Rust UI parses progress lines, paints sector map + health at ≤10 Hz.
3. Device discovery / elevation helpers stay OS-specific; ARM+x86 via `cargo` targets.
4. Do not move write paths into the UI crate — spawn/attach to the engine only.

## Operator tips

- Prefer Adaptive refresh + hybrid journal for large USB patients.
- Use `--no-live-dashboard --progress-jsonl` when a GUI owns the screen.
- Keep journals off the patient media.
