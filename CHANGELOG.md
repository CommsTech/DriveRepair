# Changelog

## 0.2.8 — Readable PowerShell CLI dashboard (2026-11-01)

- In-place color panel for live refresh (Windows VT / PowerShell / Windows Terminal); no scrolling probe wall.
- Compact throttled line mode when redirected; hide UNKNOWN health noise until data exists.
- ASCII-only status text (fixes cp1252 `…` mojibake); human `list` / scan progress bars.
- New elevated lab launcher that auto-lists USB disks for Sandisk / drive-swap testing.

## 0.2.7 — In-place media refresh safety hotfix (2026-11-01)

- Made **disk-backed** original-byte journaling the default and required it for physical drives.
- Fixed write/read-back failure paths that previously discarded the only saved region while reporting a skip. Now fail closed and keep the active transaction journal.
- Fixed crash/restart accounting for `VERIFIED`/`COMMITTED` states, and ensured adaptive queue items remain pending until committed.
- Made image refresh identity stable across intentional in-place changes by excluding file modification time from its token.
- Added live-disk journal-storage isolation checks, mounting/volume safety gates, typed destructive GUI confirmation, and Windows launcher defaults that keep the journal.
- Adaptive refresh aborts before writes if its initial probe encounters unreadable sectors.
- Auto-delete journal only after exact `completed` with no active transaction.
- Added 11 fault-injection/safety tests for interrupted writes, restart, verification, and device preflight logic.
- Live lab (USB Seagate 12 TB `PhysicalDrive2`): sample scan 24/24 OK; Adaptive 64 probes with disk journal on `D:` completed (1 MiB rewritten+verified); hybrid live backend correctly rejected.
- This is a **private-testing hardening release**, not certified for real failing media or public deployment.

## 0.2.6 — BitLocker-aware gates + reliable elevated CLI dashboard (2026-11-01)

- Fail-closed BitLocker/LUKS detection for carve/undelete/ext check-repair (`inspect-encryption`, `--ack-encrypted-volume`).
- Elevated Adaptive launcher no longer pipes stderr through PowerShell ErrorAction Stop (that killed the live UI).
- Immediate “opening patient…” stderr lines so the CLI is never blank during device open.

## 0.2.5 — Modern Recovery Workstation GUI + progress JSONL (2026-11-01)

- Replaced legacy Tk layout with an industrial dark Recovery Workstation (sector map, health strip, metrics).
- Added `--progress-jsonl` / `ProgressEmitter` (~10 Hz) so presentation stays low-overhead and GUI-friendly.
- Documented presentation vs recovery split and Rust UI migration path (`docs/PRESENTATION_LAYER.md`).
- GUI launches refresh with JSONL progress; never opens patient devices itself.

## 0.2.4 — Live refresh dashboard, hybrid RAM journal, auto-escalate (2026-11-01)

- Terminal dashboard: phase, progress bar, surface map, latency, media/transport/mechanical* indicators.
- `--journal-backend hybrid|disk|memory` (default hybrid: region bytes in RAM).
- `--auto-escalate` subdivides slow/failed probes for deeper testing.
- `--after-run keep|delete|ask` for journal retention.
- mechanical* is a latency/error proxy — USB docks do not expose acoustic sensors.

## 0.2.3 — Live Windows adaptive refresh hardening (2026-11-01) — PRIVATE TEST ONLY

- Clear Administrator requirement when Windows denies physical-drive write access.
- Adaptive probe telemetry in JSON (targets, median/threshold, probe failures).
- First elevated live adaptive run on USB 12 TB patient completed (sampled regions only).

## 0.2.2 — Rolling-journal In-Place Media Refresh (2026-11-01) — PRIVATE TEST ONLY

- Replaced simple rewrite with transactional rolling journal: `SAVED → WRITING → VERIFIED → COMMITTED`.
- Journal stores only the active region (`meta.json` + `region.bin`) on separate healthy storage.
- Added `--mode adaptive` (default; slow readable regions) and `--mode full` (whole surface).
- Consistency multi-read before rewrite; unreadable/inconsistent sectors skipped, never invented.
- Windows volume idle check + FSCTL lock/dismount when letters exist; Linux `O_EXCL`.
- Live external refresh also requires `--ack-unvalidated-hardware` until sacrificial interrupt/USB tests pass.
- Does not claim wear reversal or equivalence to a full backup.

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
