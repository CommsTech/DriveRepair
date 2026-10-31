# Changelog

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
