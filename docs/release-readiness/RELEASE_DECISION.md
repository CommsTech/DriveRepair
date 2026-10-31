# RELEASE_DECISION

**Date:** 2026-10-31  
**Branch:** `remediation/gate0-safety-2026-10-31`  
**Baseline HEAD:** `e7396368828bef08d534a1f2442d0e382243cf9e`

## Formal status

| Decision | Value |
|---|---|
| Release class | **NOT_READY** for public distribution |
| Operational class | **PRIVATE_TEST_ONLY** for the Python desktop read-only scanner + Gate 0 Rust library containment |
| Public experimental beta | **Blocked** |
| Public stable | **Blocked** |
| Better-than-SpinRite (any workload) | **NOT_PROVEN** |

## What is authorized under PRIVATE_TEST_ONLY

- Offline synthetic desktop unit tests (`desktop/tests`)
- `scan-image` against regular files / generated fixtures
- `list` / read-only `scan` of **owner-approved sacrificial external** media only, with `--ack-risk` for full mode
- Host `cargo test --features "std,alloc" --lib` on the Gate 0 fail-closed library

## What remains forbidden without separate owner approval

- Merge to protected `main` / public release packaging
- Re-enabling destructive USB/ISO writers
- Running experimental BIOS/UEFI “repair” paths on valuable disks
- Claiming sector repair, verified reconstruction, or competitive superiority
- Widening desktop discovery to internal/boot/system disks

## Evidence anchors

- Desktop delivery note (2026-10-31): 19/19 Python tests in Linux analysis env; macOS/Windows hardware **NOT_PROVEN** here until re-run
- Gate 0 Rust containment: fail-closed stubs, SMART Unknown on empty, no Repaired-on-read, USB scripts exit 2
- No top-level `.iso`; boot product **NOT_PROVEN**
- Imaging/mapfile rescue orchestration: scaffold only

## Next gates (ordered)

1. Re-run desktop + Rust CI on Windows/macOS/Linux runners; attach logs to `TEST_EVIDENCE.md`
2. Sacrificial external-device matrix; zero-write invariant on source
3. Image-first rescue with durable map (ddrescue) in QEMU/fixtures
4. Independent review before any main merge or installer
