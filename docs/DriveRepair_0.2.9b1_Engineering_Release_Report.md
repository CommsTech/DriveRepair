# DriveRepair 0.2.9b1 — Engineering changes & release disposition

**2026-11-01** | Source basis: `DriveRepair-main(2).zip` (uploaded at 09:49 Arizona time) | Status: **PRIVATE BETA CANDIDATE — NOT APPROVED FOR PUBLIC RELEASE**

## What was actually changed

1. **Device identification:** Windows discovery now prefers Get-Disk because it has system/boot indicators. Legacy WMI/CIM fallback remains informational but cannot authorize physical refresh. Disk lists include model, size, bus, masked serial, where available the controller/HCTL location, and an identity fingerprint. Physical writes require matching `--confirm-identity` from the current disk listing. Duplicate bridge serials are rejected.
2. **Experimental UPS/battery RAM-backed journaling:** A new Linux-only `ramdisk` backend writes **the current original-sector bytes AND transaction metadata** onto a RAM-backed filesystem, not process-only heap. Its preflight checks verified tmpfs/ramfs, available space, and absence of swappable journal data. It checks either locally managed USB Network UPS Tools telemetry (OL, charge >=70%, predicted runtime >=15 minutes) or Linux laptop battery (>=80%, externally powered, not discharging); repeated power guard calls precede writes. It also requires `--ack-volatile-journal` and `--ack-dock-power-backed` acknowledgments. A read-only `ram-journal-check` command permits dry-run validation. Physical RAM writes on Windows/macOS are deliberately not unlocked; no safe RAM-disk equivalence has been demonstrated.
3. **Recovery memory scaling:** the regular-file rescue first pass now creates its range jobs lazily, rather than materializing potentially millions of tuples. A sparse 12 TB synthetic image test completed its first chunk and preserved its map without allocating the full job list.
4. **Throughput knobs:** Both refresh and rescue accept 1/2/4/8/16/32/64 MiB chunks. The graphical interface exposes the refresh chunk size (default 8 MiB). Larger chunks reduce metadata and fsync counts but increase the risk and recovery cost of any single in-flight transaction. Optimal settings must be measured per hardware type.
5. **Preflight and UX:** More informative disk identification in GUI/CLI and recursive Linux partition holder checks. An active encrypted/RAID/mapper partition cannot be treated as an idle parent disk simply because it is unmounted.
6. **Packaging:** version 0.2.9b1, synchronized zipapp and wheel build script; additional CI smoke step. Complete source ZIP excludes stale Rust `target/` and generated Python build artifacts from the uploaded archive. Source deliberately contains no proprietary competitor names; technical comparison here is separate from product files.

## Tests executed

- `PYTHONPATH=desktop python -m unittest discover -s desktop/tests -q`: **105 discovered, 104 passed, 1 platform-specific skip** on Linux, zero failures.
- `python scripts/build_desktop.py`: **succeeded**, including test suite, compileall, portable zipapp help smoke, wheel build.
- `git apply --check`: passed against a clean snapshot made from the provided ZIP, and applied contents verified byte-for-byte for changed/new files.
- Synthetic forced torn write under new `ramdisk` journal: durable (within the mock host) region file persisted, a fresh recovery object resumed, data matched original.
- Simulated power-guard refusal stopped before a patient write while preserving the journal's original region.
- Local NUT telemetry acceptance/rejection mocked for utility-line and low-battery states. **No real UPS was attached.**
- Linux memory-test: sparse 12 TB image could begin rescue without generating 12 million jobs.
- All tests operated on files, mocks or synthetic inputs; **no physical drive writes**, no real USB disconnect, no UPS behavior, no Windows/macOS execution tests, and no Rust build in this environment.

### Preliminary refresh throughput microtest (NOT a drive comparison)

16 MiB synthetic regular-file source, disk journal, full refresh, 2 pre-read consistency reads + write + read-back and original SHA-256 match:

| Transaction size | Wall time | Outcome |
|---|---:|---|
| 1 MiB | 0.399 s | Same SHA-256 |
| 8 MiB | 0.201 s | Same SHA-256 |
| 16 MiB | 0.186 s | Same SHA-256 |

This is an **illustrative OS/filesystem cache test**, not a USB, HDD, SSD, RAM-journal, or hardware-recovery benchmark. It does not establish higher physical throughput or improved lifespan. Real 12 TB duration depends on speed, error recovery, power and USB behavior, metadata overhead and the number of passes.

## Critical missing capabilities — first public beta release still BLOCKED

**P0 (blocker):** Sacrificial USB dock/hot-unplug, torn-write and power-off tests with actual SATA/USB bridges; Windows Get-Disk and raw-volume lock tests; failure injection while SAVED/WRITING/VERIFIED; journal identity and destination ancestry; protected device and partition-mapper coverage. USB bridges can fake or mask serials and health information. A battery/UPS does NOT guarantee the host, hub and dock all survive interruption.

**P0 (blocker):** Independent, *same-initial-condition*, sector-hash-verified recovery benchmarks against GNU ddrescue and OpenSuperClone; file recovery tests against TestDisk and PhotoRec. Do not use sequential stress runs on the same deteriorating disk and call it a fair comparison. Track bytes correctly recovered, false successes, source write counts, throughput, P95 read latency, wear/SMART changes, read amplification and failure-mode outcomes.

**P0 (blocker):** Dedicated Windows/macOS installation, discovery and read scan test matrix, plus real Linux direct-device tests. The Python wheel is not a native Windows EXE or macOS APP; Tk may require separately installed GUI components.

**P1:** The desktop recovery core is Python; current Rust code is a separate experimental boot tree. A Rust I/O hot path could improve scheduling, aligned buffer management, fixed-memory queueing, map encoding, checksum throughput and overhead, but **cannot fix physical read errors** or replace sophisticated data-rescue passes. A small Rust core with Python CLI/GUI wrapper is a sensible migration path; prioritize deterministic results over novelty.

**P1:** Add multi-pass rescue (skip slow zones, reverse reads, trim edges, scrape once, carefully bounded retries), resumable map with source identity, SSD/SMR/NVMe policies and transport error classification. Consider optional use of an installed, separately licensed recovery executable for mature algorithms rather than copying them under MIT.

**P2:** File system-aware undelete with NTFS/exFAT/ext/APFS, fragmented-file reconstruction from metadata, deleted directory tree/names, file content validation and media-format repair. Current PNG/JPEG/ZIP, FAT32-contiguous and ext-clone workflows are limited.

**P2:** Guided workflow/wizard and simplified onboarding: identify disks with physical cues, distinguish *recover data* vs *refresh media* vs *filesystem repair*; show risks, storage requirements, ETA ranges, target summary, skipped/unverified sectors and recovery export; block accidental writes to system/array members. Signed installers, reproducible builds, versioned release artifacts, security report and supported-hardware matrix.

## Safety details for RAM option

- The active original bytes are preserved on a RAM-backed filesystem and should survive **application process exit while host RAM remains intact**; no protection against host restart, kernel panic, disconnected USB dock or failing media.
- Linux only in this build, and only if the journal mount is tmpfs/ramfs and does not swap. Requires a user-configured local USB NUT UPS **or** Linux laptop battery telemetry. A fully charged laptop does not mean an externally powered USB dock is battery-backed; the separate acknowledgment covers this uncertainty.
- Loss of verified power halts the next write operation; an already-active write can still fail. Always use an ordinary disk journal by default, unless the operator explicitly trades durability for speed.
- Recovery from unreadable sectors remains separate from in-place rewriting: never fabricate bytes or overwrite irreplaceable unreadable source data automatically.

## Artifacts

- `DriveRepair_0.2.9b1_Beta_Candidate_Source.zip`
- `DriveRepair_0.2.9b1_Changes.patch`
- `DriveRepair-0.2.9b1.pyz`
- `driverepair_desktop-0.2.9b1-py3-none-any.whl`
- `DriveRepair_0.2.9b1_Engineering_Release_Report.md`

## Authoritative references consulted

- GNU ddrescue 1.30 manual (2026): https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
- OpenSuperClone: https://github.com/ISpillMyDrink/OpenSuperClone
- TestDisk/PhotoRec documentation: https://www.cgsecurity.org/testdisk_doc/index.html
- NUT UPS states and driver documentation: https://networkupstools.org/docs/user-manual.chunked/ar01s06.html
- Windows Get-Disk and battery API: https://learn.microsoft.com/en-us/powershell/module/storage/get-disk and https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getsystempowerstatus
