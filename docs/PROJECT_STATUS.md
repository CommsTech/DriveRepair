# Project status — 2026-11-01

**PRIVATE TEST ONLY. PUBLIC RELEASE NOT APPROVED.**

## Desktop development update — 0.2.0

- GUI: implemented with stdlib Tk and CLI subprocess workers, not yet smoke-tested on physical Windows/macOS/Linux desktops.
- FAT32 undelete: implemented for plausibly contiguous, unallocated cluster sequences from raw volume or MBR FAT32 image; every recovered file marked **UNVERIFIED**. Does not recover original first filename letter, fragmented or overwritten files.
- Image correctness: added whole-file SHA-256 and bytewise comparison against a stable original image; refuses sparse/incomplete recovery journals.
- Filesystem repair: implemented an ext2/3/4 workflow that clones a regular filesystem image and runs installed `e2fsck -f -y` **only on the clone**, after explicit acknowledgment. No physical-source writes or in-place drive repair.
- The expanded synthetic suite passes 65 tests in this environment; no actual HDD/SSD hardware tests and no Rust boot build were performed here.

## Verified in source and synthetic tests

- External-drive discovery (existing mock tests), read-only surface scans.
- Restartable, sector-aligned image rescue with a durable sparse-output map, targeted retry, conservative source identity checking, and failure propagation.
- Linux-only experimental external-disk rescue with separate-destination mount ancestry checks.
- Read benchmarks, sampled latency and comparison across same-source measurements.
- Optional smartctl JSON health snapshots with unknown/failing status handling; no silent healthy result from missing data.
- PNG/JPEG signature carving from regular-file images, with PNG chunk CRC verification.
- Intact-member extraction from partially corrupted ZIP archives using standard-library ZIP CRC verification.
- Windows host portability for image workflows: binary `O_BINARY` opens, portable `pwrite` fallback; **65 unit tests passed** on Windows workstation (2026-11-01).

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

P4: Validate desktop GUI on real Windows/macOS/Linux, provide signed native installers, bootable Linux distribution, reproducible builds and release docs.
