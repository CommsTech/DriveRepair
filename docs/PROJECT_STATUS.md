# Project status — 2026-11-01

**PRIVATE TEST ONLY. PUBLIC RELEASE NOT APPROVED.**

## Verified in source and synthetic tests

- External-drive discovery (existing mock tests), read-only surface scans.
- Restartable, sector-aligned image rescue with a durable sparse-output map, targeted retry, conservative source identity checking, and failure propagation.
- Linux-only experimental external-disk rescue with separate-destination mount ancestry checks.
- Read benchmarks, sampled latency and comparison across same-source measurements.
- Optional smartctl JSON health snapshots with unknown/failing status handling; no silent healthy result from missing data.
- PNG/JPEG signature carving from regular-file images, with PNG chunk CRC verification.
- Intact-member extraction from partially corrupted ZIP archives using standard-library ZIP CRC verification.
- Windows host portability for image workflows: binary `O_BINARY` opens, portable `pwrite` fallback; **48 unit tests passed** on Windows workstation (2026-11-01).

## Not verified

- Hardware operation across Windows, macOS and Linux; Linux physical rescue has **not** been hardware-tested.
- User data recovery effectiveness on damaged real media; stress/retry budgets may need optimization.
- Linux destination-isolation logic in complex storage setups, including nested device mapper / encryption / multipath.
- Proprietary recovery algorithm parity, competitive benchmark outcomes, deep filesystem repair, data-carving completeness.
- Raw-drive write support, in-place repair, media refresh, actual flash/endurance rejuvenation.
- Bootable disk image integrity and Rust bootloader integration.

## Safety boundary

Desktop never requests a write handle on a source drive. Media remapping/refresh operations **remain disabled** pending separate design review, independently verified backups, and real-drive testing. Bootable Rust experiments are not production-ready.

## Next engineering milestones

P0: Add independent Linux and Windows/macOS device-mapping verification; actual bench hardware test matrices, fail-safe cancellation, read timeouts and mature multi-pass rescue scheduling.

P1: Validate optional smartctl SMART/NVMe snapshots on real hardware and add manufacturer-aware interpretation; add per-LBA latency maps, integrity hashes, and optional external proven rescue engine adapter without copying licensed code.

P2: Build metadata-aware undelete on FAT/exFAT/NTFS/ext4/APFS as read-only plugins; enhance format-aware recovery of damaged archives and media files.

P3: Develop a **separately authorized** media-refresh / targeted-remap experiment only for backed-up, non-critical disks; evaluate outcome using randomized before/after measurements and drive health indicators. Do not market improvements as physical-wear reversal.

P4: Native desktop GUI, properly signed installers, portable bootable Linux distribution, reproducible builds and release docs.
