# Test evidence

**Rule:** Never invent PASS. Unrun work is SKIPPED / NOT_PROVEN.

## Maintainer workstation (2026-10-31, Windows)

| Command | Exit | Result |
|---|---|---|
| `cd desktop && py -3 -m unittest discover -s tests -v` | 0 | 19 passed |
| `cargo test --features "std,alloc" --lib` | 0 | 43 passed, 3 ignored |
| `cargo clippy --features "std,alloc" --lib -- -D warnings` | 0 | PASS |
| `py -3 -m driverepair_desktop list --json` | 0 | `[]` (no qualifying external disks present) |
| Physical sacrificial USB matrix | — | **SKIPPED** / pending |
| QEMU bootable product ISO | — | **SKIPPED** (no product ISO) |
| Linux `dm-dust` / `dm-flakey` / `dm-delay` | — | **SKIPPED** (Linux lab) |

## CI

`.gitea/workflows/ci.yml` runs fmt, clippy, Rust lib tests, and desktop unit tests on Linux/Windows/macOS runners (runner availability depends on forge configuration).
