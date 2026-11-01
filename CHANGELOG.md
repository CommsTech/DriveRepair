# Changelog

## 0.2.1 — Experimental in-place refresh (2026-11-01) — PRIVATE TEST ONLY

- Added gated `refresh-image` / `refresh-external` commands: read → rewrite same bytes → optional verify.
- Unreadable sectors are skipped and never overwritten with fabricated data.
- Requires `--ack-risk --ack-destructive --ack-no-backup --ack-data-loss-risk` (+ `--ack-usb-bridge-risk` for USB/dock).
- Does not claim physical-wear reversal; journaled and resumable.

## 0.2.0 — Desktop workflow and clone-only repair (2026-11-01) — PRIVATE TEST ONLY

- Added Tkinter graphical desktop frontend with asynchronous commands, cancellation, device discovery, external scans, health, read benchmarks, rescue, ZIP salvage and file recovery.
- Added conservative FAT32 deleted-file recovery from raw or MBR image; refuses allocated clusters, explicitly flags every recovery as unverified.
- Added ext2/3/4 filesystem integrity check and optional **clone-only** repair through an installed `e2fsck` utility, never an in-place device repair.
- Added byte-accurate regular-image verification with SHA-256 and refusal of incomplete rescue maps.
- Added GUI/`pyz` packaging via `scripts/build_desktop.py` and wheel entry points `driverepair-desktop` / `driverepair-gui`. Synthetic unit coverage expanded to **65** tests.
- No live hardware sector-write functionality or unverified media rejuvenation feature is enabled. Public release not approved.

## 0.1.0-alpha — 2026-11-01 (PRIVATE TEST ONLY)

- Added image-first sparse rescue with atomic journal checkpoints, restartability, and a separate targeted-retry pass.
- Added Linux external-source rescue with conservative mount/holder and destination block ancestry safeguards; Windows/macOS image-only recovery remains available.
- Added read-only latency-zone benchmarks and same-device before/after comparison.
- Added PNG/JPEG image carving and intact-member ZIP salvage; both write new output files only.
- Added optional read-only smartctl health snapshots.
- Added Windows binary-I/O portability (`O_BINARY`, portable `pwrite`) so image rescue/carving pass on Windows hosts.
- Added media refresh R&D design and honest release-readiness documentation.
- No physical-disk write/refresh/repair command enabled; no hardware recovery claims; public release not approved.

## 0.0.1 — public experimental (2026-10-31)

### Added

- Cross-platform **read-only** desktop scanner (`desktop/driverepair_desktop`) for Windows, macOS, and Linux
- External whole-disk discovery via OS tools; exact ID selection; identity recheck
- Sample and full surface scans with JSON output and bounded error stops
- Synthetic unit tests (no physical disks required)
- MIT `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, honest public README
- Gate 0 Rust library fail-closed behavior for unimplemented I/O

### Changed

- Host Rust launcher no longer offers misleading repair workflows; points to the desktop scanner
- Destructive USB provisioning scripts hard-disabled (`exit 2`)
- Documentation rewritten for public experimental release; obsolete overclaim materials removed

### Not included

- Sector repair / remapping / TRIM / erase
- Production BIOS/UEFI recovery media
- Signed desktop installers
- Guaranteed SMART health from hardware
