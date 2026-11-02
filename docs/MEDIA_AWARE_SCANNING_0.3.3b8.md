# DriveRepair 0.3.3b8 — Media-aware scans, repairs, and acceptance testing

## What changed and what did not

A USB, Thunderbolt or SATA connection **does not** tell DriveRepair whether the underlying disk is SMR, CMR, SSD or NVMe. The program uses an exact manufacturer-identified model where supported (`ST1000LM048`, `ST500LM030`, `ST500LM034`), then explicit recording/medium evidence; it otherwise reports `unknown`. This version intentionally has no probabilistic “CMR” inference from latency alone. Seagate BarraCuda 2.5 datasheet DS1907 lists the ST1000LM048 1 TB as **SMR, 512 logical / 4096 physical-byte sectors**. Manufacturer reference: https://www.seagate.com/www-content/datasheets/pdfs/barracuda-2-5-DS1907-3-2005US-en_CA.pdf

### Behavior table

| Confirmed medium | First-pass reads | Suspect follow-up | Patient rewrites |
|---|---|---|---|
| SMR | Aligned, larger batched reads; avoid repeated random scanning | Bounded smaller reads, delayed from main pass | Only independently reread/journaled target; **no automatic neighbor writes** |
| CMR | Aligned sequential/stratified reads; adaptive larger reads | Smaller reads plus left/right inspection | Verified targets; optional explicit `--recording cmr --rewrite-neighbors` requires extra consent |
| SSD / NVMe | Prefer health, endurance, error-log evidence and read-only integrity checks | Bounded smaller reads | No automatic adjacent rewrites; flash wear and FTL translation cannot be “reversed” by host writes |
| Unknown / USB bridge | Conservative read calibration; do not assume recording type | Record distinct media vs transport errors | No profile alone authorizes writes |

**Caution:** adjacent *logical* addresses may not be on adjacent physical tracks, and an SMR write may trigger a large internal band rewrite. NVMe controller-managed remapping and SSD NAND endurance make “rewrite next door” an unreliable generic repair rule.

## Quick Repair = 10% unique address coverage

Quick Repair deliberately reads **at least 10% of the source logical address space**. It uses a deterministic stratified pseudo-random set of aligned probes distributed across the whole drive, processed in address order to reduce unnecessary seeks. The sample is reproducible; it is not a statistical certificate of the unvisited 90%. Unique coverage is reported separately from bytes read during retries or initial calibration.

At 120 MiB/s, 100 GB of raw data is a theoretical minimum of about 13 minutes, excluding seek, USB reset, retry and throttling overhead. Multi-TB Quick Repair can be much longer. The application should state these costs to users rather than silently reducing the requested percentage.

Full Repair uses a short early *read-only* calibration (up to five progressive reads) to select a reasonable initial transfer size and then dynamically adjusts between bounded media-aware limits. A blocked or failed initial read ends calibration early. Full scanning skips/delays difficult regions for later sector-aligned smaller requests; it never converts a failed read into verified data.

### Left/right checks and reconditioning

For eligible slow but repeatably readable target regions, DriveRepair checks short immediate left and right windows with two separate reads. Error-bearing or inconsistent windows are excluded. This check **does not prove original bytes are correct**, nor does it authorize a write. Only an explicit advanced CMR recording declaration plus `--rewrite-neighbors` permits verified neighbors to be appended to the already explicit in-place repair transaction. SMR, SSD, NVMe and unknown media cannot use that option.

No arbitrary unreadable sector is overwritten or reinitialized. There is no physical platter smoothing, firmware update, defective NAND repair or universal “like new” certification.

## Windows USB-dock reliability

PowerShell `Get-Disk` can hang when an external drive or its bridge is failing; CIM and WMIC may also time out. After an earlier verified selection, a selected-drive query (`Get-Disk -Number N`) now avoids full inventory when possible, **but still needs the OS to respond**. All raw-drive writers require fresh authority, capacity, serial, identity and offline/volume safety checks. A cached GUI selection or a test result **cannot bypass** them. If the post-scan identity query fails, DriveRepair returns the collected scan and a `repair_blocked_identity_recheck` result with zero writes.

For real hardware, first check Windows Event Viewer > System storage/disk events, USB power, cable, and a known-good direct SATA connection if practical. A prior `WinError 1117` means I/O device error, not proven media failure. Do not retry indefinitely on irreplaceable data.

## Public beta acceptance gates (not yet met)

- [ ] Native Windows discovery tests, selected-disk re-identification, USB disconnect / 1117 / timeout injection.
- [ ] Safe pre-write locking and no-active-volume tests on Windows, macOS and Linux.
- [ ] Sacrificial SMR/CMR/SSD/NVMe stress tests, including deliberate interruptions and simulated power loss.
- [ ] Comparison with ddrescue and professional recovery tools on identical failing-media fixtures.
- [ ] SMART/firmware detection through USB bridges; never flash firmware automatically.
- [ ] Operator-guided GUI clickthrough across Windows DPI scales and low-resolution laptop displays.
- [ ] Rust core compilation, mixed Python/Rust integration and a validated BIOS/UEFI recovery ISO.

This code is **engineering beta only**. Synthetic tests cannot establish media repair safety or recovery superiority.

**RAM-only versus history:** RAM-only keeps sector data and transaction state in process RAM and never saves a recovery image or sector journal. An independently selected “Remember bad/slow locations” option may save a small, local, offsets-only diagnostic history on the host computer. It stores no sector bytes, file contents, or write authorization. Disable it when absolutely no diagnostic files are desired.

**Repeat Quick Repair:** Each physical-drive session uses a new recorded random sampling seed. The selected locations are stratified across the disk and processed in address order; a repeat run can inspect different areas. Saved anomaly locations (when enabled) are rechecked separately. A new seed does not establish full-disk integrity. Synthetic image tests retain deterministic sampling.
