# DriveRepair 0.2.9b1: beta candidate, NOT release approved

2026-11-01 · Source ZIP provided by owner · Synthetic-only verification

## Research and capability gaps

Current desktop code is primarily **Python**, not a Rust-optimized cross-platform recovery core. Rust in `src/` is an experimental/legacy boot implementation, not the active desktop I/O path. Therefore a claim that all recovery is currently written or accelerated in Rust would be misleading.

* **GNU ddrescue (manual v1.30, January 2026)** uses copying, trimming, sweeping, scraping and retries, a compact map, skip-ahead of slow areas, reverse passes and optional direct I/O. DriveRepair's image rescue currently uses a fast first pass plus targeted retries but lacks several of these tested heuristics. Test against ddrescue before claiming faster/more accurate recovery: https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
* **OpenSuperClone** includes difficult-device reset/control strategies and advanced imaging. DriveRepair does not implement those reliably: https://github.com/ISpillMyDrink/OpenSuperClone
* **TestDisk / PhotoRec** implement partition analysis, filesystem recovery and hundreds of carving signatures. DriveRepair only offers conservative FAT32 contiguous undelete, PNG/JPEG carving and ZIP member salvage: https://www.cgsecurity.org/testdisk_doc/index.html
* **UPS/NUT** has documented `OL`, `OB`, `LB`, shutdown and USB driver status. A local UPS report alone cannot prove the dock is plugged into UPS power: https://networkupstools.org/docs/user-manual.chunked/ar01s06.html
* Some USB-SATA bridges mask or fabricate serials and SMART information. Transport errors are not evidence of damaged magnetic media; bad blocks and SMART are never automatically marked healthy from unavailable data.

## Implemented in this candidate

| Area | Implementation | What remains unproven |
|---|---|---|
| Drive selection | ID + model + decimal GB + masked serial + bus + OS location hint + 12-character fingerprint; typed target + exact fingerprint before raw writes; reject duplicate bridge serial | Real replug/disconnect tests, Windows Get-Disk identity under all dock types |
| RAM journaling | Linux tmpfs/ramfs original bytes+meta, no-swap preflight, UPS/battery checks, runtime monitoring, write preflight, explicit risk acknowledgments | Physical USB dock/UPS behavior, sudden kernel crashes, platform support on Windows/macOS |
| Throughput | 1–64 MiB regions, GUI chunk option, bounded-memory 12 TB rescue scheduling | Benchmarks vs 1 MiB, recovery gain on failing media, HDD vs SSD vs SMR tuning |
| Safety | Linux recursive holder checks, stable fingerprint, no silent success on write/readback mismatch | Zoned drives, HBA/RAID, NVMe namespaces, transport reset tests |
| Product | Portable desktop package + Python wheel + CLI/GUI | Standalone signed .exe/.app/.deb, verified portable distribution, bootable recovery parity |

## RAM mode threat model

RAM-only original-sector journaling is **inherently less safe** than a journal written to healthy durable storage. UPS/laptop battery reduces one failure mechanism; it does not protect against host kernel panic, application crash that destroys heap data, machine restart, firmware errors, or loss of USB-dock power. This release uses **RAM-backed filesystem storage** so process crashes can leave the region and metadata accessible *while the host remains up*. Linux swap is checked to avoid silently writing bytes to other drives. In-place operations still require `--ack-volatile-journal` and `--ack-dock-power-backed` because software cannot attest dock wiring. If power reports low or unknown, DriveRepair refuses to start another write. Power can still fail during an already active write.

For physical drives, journal storage must never share physical source storage. A rolling journal only protects a single in-flight region and is not a whole-disk backup. Every repaired byte is checked against a previously read copy, not against an independent ground truth. Software cannot reverse worn NAND cell endurance or damaged heads/platters.

## Remaining P0 release blockers

1. **Real hardware:** >10 TB USB docks (multiple bridges), 512e/4Kn, USB disconnect during SAVED/WRITING/VERIFIED, loss of power and resume; sacrificial disks only. Confirm no wrong-patient writes, no silent changes and no false success.
2. **Recovery effectiveness:** benchmark ground-truth known image data and real damaged media against ddrescue, OpenSuperClone, TestDisk/PhotoRec under identical initial conditions. Compare verified bytes, false recovered bytes (must be zero), mean/P95 times, read amplification, operator errors and power faults; do not invent superiority results.
3. **Platform coverage:** run desktop GUI and actual USB read scans on Windows/macOS/Linux, Windows raw-drive write locks and Get-Disk identity, package signed native bundles. RAM mode is Linux only.
4. **Performance/accuracy:** design robust Rust native read/imaging engine with fixed-size aligned buffers, bounded queuing, per-region checksum/verification, adaptive skip-ahead and reverse retries; never increase retries on failing disks without a stop policy. Benchmark direct I/O vs buffered I/O per device. Do not depend on obscure abstractions or unverified low-level hardware commands.
5. **Filesystem features:** complete a filesystem-aware, read-only NTFS/exFAT/ext/APFS/MFT/journal extraction flow, original-name/metadata recovery, fragmented files, secure handling of encrypted data, format-aware verification and output provenance. Consider **optional** separately installed tools instead of copying copyleft internals under an MIT license. Never write recovered files onto the patient.
6. **Device safety:** cover all partitions/holders, multi-path mapper ancestry, swapping drive labels, missing/duplicate serials, Windows raw-IO mapping, and destination/overlay volume ancestry. Device fingerprint derived from OS fields cannot replace authoritative hardware identity.
7. **Usability:** scenario wizard (rescue / refresh / deleted file / health), preview of source-vs-destination path, show risk class, expected data and spare space, SMART caveats, resumable session list, signed installers, tool diagnostic report with sanitized serials.
8. **Build and supply chain:** verify Rust core separately; reproducible builds, dependency audit, SBOM, signed artifacts; CI on all three OSes; security review and vulnerability-report policy.

## Beta gate outcome

`PRIVATE_BETA_CANDIDATE / NOT_APPROVED_FOR_PUBLIC_RELEASE`. Synthetic tests and packaged CLI smoke do **not** demonstrate cross-platform hardware safety or superiority. Do not advertise proven restorative performance or call full-device rewrite 'like new'.
