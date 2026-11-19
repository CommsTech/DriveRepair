# DriveRepair 0.3.3b14 — media-aware recovery workbench

Date: 2026-11-18. **Hardware qualification: NOT COMPLETE.**

## Implemented in this revision

- Qt workbench has a condensed navigation and progress hierarchy: five visible KPI cards in one row instead of two rows of six, single progress bar on non-guided operations, compact left-side forms, and a vector three-stage decision ribbon. Source/target choice, write risk and results remain visible and accessible. Native Windows PySide6 rendering still needs visual QA.
- The selected physical device triggers one bounded, isolated, read-only SMART probe when idle. Results are cached by the exact device fingerprint hint; stale results are never applied to a different selection. A USB bridge timeout/failure remains UNKNOWN. The probe does not retry automatically and is stopped when starting a job.
- SMART results now retain NVMe controller protocol evidence even behind a USB bridge. GUI media classification uses these health results where available rather than just the USB bus and model name. The lower-level repair preflight still independently re-reads identity and health before any write.
- Exact-model SMR evidence is retained for the known `ST1000LM048`, `ST500LM030`, `ST500LM034` entries. These entries do not license assuming that other family members are SMR. Contradictory explicit CMR/SSD/NVMe evidence resolves to **UNKNOWN**, never to a write-capable CMR profile.
- A model labeled SkyHawk, Purple, or Toshiba S300 may indicate an **NVR/surveillance workload**, but recording technology remains independently determined. NVR is not a physical medium and a product family can contain both SMR and CMR capacities.
- Classifier now accepts reported removable **flash** media distinct from SATA SSD/NVMe. A USB bus by itself does not mean flash or spinning disk.
- Both GUI quick and full scan selection use media-specific logical scan-window plans. Windows raw physical reads are internally split into <=1 MiB `ReadFile` requests, so the logical sampling/coverage contract remains intact. This reduces oversized USB requests but **does not interrupt a stuck kernel operation**.
- Read-only investigation of failed extents now lazily subdivides suspect ranges before issuing any read larger than 64 KiB, with fixed retry/time budgets. A single huge failed extent does not generate a huge Python list. Cooperative time budgets cannot preempt a driver-blocked call.
- The hardware repair planner refuses HDD-style refresh of identified SSD/NVMe/flash media, including in engineering builds. SMART rotational evidence is required for guarded HDD repair. All journal/exclusive access, digest and postverification checks are retained.
- Scan JSON results now disclose observed medium evidence, confidence, planned read window and read-only repair restrictions.

## Evidence-based decision table

| Evidence-confirmed medium | First priority | Investigation / repair treatment | Safe claim |
| --- | --- | --- | --- |
| CMR HDD | image to healthy storage, sequential scans | bounded repeat reads, verified journaled rewrite only for eligible readable regions after consent | selected reads and written bytes verified; **not** lifespan restored |
| SMR HDD (exact model/recording evidence) | image first, sequential pass | avoid adjacent random writes, small isolated optional HDD transactions with journal and identity checks | no physical SMR band knowledge claimed |
| Rotational HDD, recording unknown | image first | conservative follow-up reads; **never infer CMR** | HDD class, unknown recording |
| SSD / NVMe | back up/image, inspect controller health and wear | read-only rescue/verification, controller diagnostics; no magnetic surface refresh | flash translation / remap behavior remains controller-owned |
| Removable USB/SD flash | image readable data before further wear | small bounded follow-up reads and report unrecovered bytes; no HDD rewrite | controller and underlying NAND health often unavailable |
| NVR surveillance HDD | prioritize full sequential image where important video is present | still classify its recording as CMR/SMR/unknown independently | workload class only |
| Unknown/contradictory | read-only imaging and capture more evidence | no physical writes | UNKNOWN is not a healthy or repairable classification |

## Boundaries

- No trained neural reconstruction model is present; no inference of physically unreadable bytes. Repeatable reads are not cryptographic correctness without external reference data. RAID reconstruction requires parity/redundant members; the ARIES protocol handles transactional databases and is not a generic raw-drive repair algorithm.
- **Actual failing-drive repair, Windows USB I/O cancellation, SSD endurance changes, USB-NVMe passthrough, Linux/macOS GUI appearance, and real boot image remain unverified.**
- No arbitrary firmware flash, ATA secure erase, TRIM, sanitize, unrestricted remap, or filesystem write repair is added to the generic physical writer.
- No Rust physical-device I/O was substituted without compiling and native hardware verification. Python shell/Qt remains a controller of independent CLI processes. Rust image-only engine remains opt-in.
- Before hardware testing: verify image/destination separation, cable/bridge identity stability, SMART before/after, independent image checksums, and safe recovery from interruption on **sacrificial drives** only.

## Research sources consulted

- [GNU ddrescue manual](https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html): sequential-first rescue, skip past bad regions, bounded retry/mapfile behavior
- [smartmontools smartctl manual and USB bridge notes](https://github.com/smartmontools/smartmontools/blob/main/src/smartctl.8.in): NVMe/ATA behind USB and limitations of auto detection
- [Microsoft NVMe SMART health](https://learn.microsoft.com/en-us/windows/win32/api/nvme/ns-nvme-nvme_health_info_log): spare, media errors, percentage used and reliability warnings
- [Seagate SkyHawk surveillance line](https://www.seagate.com/products/video-analytics/skyhawk-hard-drive/) and [WD surveillance storage](https://www.westerndigital.com/solutions/surveillance): surveillance recording workload; not a single recording medium type

## Independent hardware/UX QA handoff

1. Windows 11 native Qt with 100%, 125%, 150% and 200% display scaling; check compact cards, pipeline rendering, keyboard focus, scrolling and meaningful error messages.
2. USB SSD with NVMe SMART passthrough, SATA SSD in USB bridge, known Seagate SMR HDD, documented CMR HDD, removable flash stick, SkyHawk/Purple surveillance HDD. Record actual model/serial suffix, protocol, confidence, recommendation and gate outcome. No family-name inference.
3. USB bridge without SMART/serial: ensure 'unknown' stays unknown and no physical writes are authorized. No repeated automatic SMART probes or auto-refresh after timeout.
4. Windows raw USB reads: instrument each kernel ReadFile request and confirm <= 1 MiB. Inject short reads, access denied, physical-disk removal, and stalled requests. Source cannot be safely disconnected during writes.
5. Read-only investigation of 1 MiB error ranges and huge synthetic extent: verify each subread <= 64 KiB and no unbounded queue/memory growth, correct unresolved data accounting, and no fabricated recovery.
6. Guarded HDD repair with a **sacrificial** compatible drive and separate journal: baseline SMART/image, exclusive lock, bounded writes to eligible repeatably readable regions, two independent postwrite reads and digest, final SMART. Confirm controller remap only if actual counters demonstrate it; even then do not call drive 'as new'.
7. Directly attempt CLI care-external on SSD/NVMe/flash and conflicting identities in engineering and guarded builds. It must reject unqualified writes. No simulated bypass should ship.
8. Perform clean bootable-USB qualification separately. No ISO is included or produced by this revision; an ISO build recipe or staged hash does not prove BIOS/UEFI bootability.
