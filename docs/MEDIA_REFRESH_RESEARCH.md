# Media refresh, weak-sector repair and physical-wear claims

**Research update: 2026-11-01.** This is a technical feasibility note, not a certification of any product claim.

## Mechanisms distinguishable in software

1. **Magnetic signal refresh:** A sector may contain marginally readable bits even though the physical surface is intact. A successful read followed by rewriting the **verified source data** can strengthen the recording. This is a real physical change in recorded magnetization, **not repair of damaged platter material, heads, motor or electronics**.
2. **Drive-managed sector relocation:** A read/write/verify cycle may cause the HDD controller to allocate a spare sector for an unreliable LBA. The visible LBA may then read reliably, but the original damaged spot has not been healed. Firmware may remap or retire blocks; triggering this after data loss destroys the ability to recover the original location.
3. **SSD read disturb / retention refresh:** Refreshing still-readable NAND data can improve retention and read speed; vendor documentation explicitly recommends refresh for read-disturb. This does **not** replenish NAND program/erase endurance, and indiscriminate rewriting introduces additional wear and may disrupt filesystem TRIM behavior.
4. **Filesystem repair:** Correcting metadata or copy-on-write references can restore accessibility of files while not improving media physical reliability.
5. **Thermal and transport optimization:** Cable, USB bridge, firmware settings, temperature and power can improve reported error rates and performance without repairing media.

## Primary sources

- Micron NAND FAQ, read-disturb / refresh guidance: https://www.micron.com/sales-support/sales/faqs
- Micron endurance white paper, flash program/erase wear: https://www.micron.com/content/dam/micron/global/public/products/white-paper/5210-ssd-vs-hdd-endurance-white-paper.pdf
- Seagate, bad-sector spare relocation and data-loss warning: https://www.seagate.com/support/kb/how-do-i-low-level-format-a-sata-or-ata-ide-hard-drive-203931en/
- Seagate, interpretation and seriousness of SMART warnings: https://www.seagate.com/support/kb/my-system-reported-a-smart-error-on-the-drive-184619en/
- GNU ddrescue, proven multi-phase image-first algorithm: https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html

Additional research: modern NAND controller design can internally adjust read reference voltages and perform retention-error mitigation or in-place charge refresh. These operations generally require flash-controller/firmware support and are **not** exposed as standard block-device sector read/write commands. Media-level correction is distinct from host-level repair.

- Academic controller-level flash recovery study: https://www.mdpi.com/2079-9292/14/4/738
- smartctl device telemetry semantics (exit bitmask): https://github.com/smartmontools/smartmontools/blob/main/src/smartctl.h

## Hypothesis-driven rejuvenation lab

**Safety constraints:** sacrificial hardware only; two independent verified backups of valuable content; no production storage; drive not mounted or in an array; independent human approval for all original-drive writes. Hardware-lab authorizations and read-only rescue are separate. Never imply physical damage is reversible.

A. Baseline: measure health attributes/SMART, NVMe wear %, sector latency map, pre/post temperature, read errors, slow-region fraction and throughput. Record model, firmware, serial hash, bus, block size, and environment.

B. Acquire a complete byte image to separate healthy storage with a recovery map. Validate known per-file hashes if available. If source has unreadable sectors, do **not** overwrite those locations until recoverability is resolved and owner authorizes loss.

C. Control group: comparable model/firmware drives undergo read-only scans. Experimental group: **only selected, already recovered and backed-up regions** receive explicitly approved refresh/verify writes. Do not make unsupported raw-device writes using the current desktop CLI.

D. Observe: randomized sequence repeated readings with cold-cache controls, p50/p95/p99 slow-sector latency, SMART raw counters, media errors, data hashes, endurance consumption and week-later persistence.

E. Gate success: every affected data region was restored byte-perfect from a verified copy; read-back matches; no increase in media errors; statistically meaningful sustained change compared with control; no dangerous write amplification. Report 'media refresh improved read performance on these samples' not 'physical wear reversed'.

F. Failure: any unexpected disconnect, rising reallocated/uncorrectable counts, thermal runaway, changed device identity, checksum disagreement, write failure or loss of source data halts experiment and recommends replacement.

## Architecture R&D directions

- Adaptivity: read speed and retry limits depend on error and slow-read density, power, transport and head/zone behavior; prioritize salvage of easy regions before hammering poor ones.
- Integrity: correlate recovery maps with filesystem metadata and checksums; use redundant known-good copies for actual byte reconstruction; do not reconstruct unknown bytes by guesswork.
- Media type: HDD CMR/SMR, SATA SSD, NVMe, USB thumb drives and SD cards need distinct write/refresh policies. Do not blanket-rewrite all media types.
- Measurement: track **data correctness**, **remaining hardware wear**, **risk of further damage**, **time to recover**, and **workload performance** independently.

**Current code** implements measurement, source-preserving rescue, and an **experimental** gated in-place refresh (`refresh-image` / `refresh-external`) that rewrites only fully readable chunks after multiple acknowledgements. It is PRIVATE TEST ONLY, does not claim wear reversal, and must not be treated as a substitute for imaging when a verified backup destination exists.
