# Changelog

## Unreleased — 2026-11-19 USB capacity-integrity spot test and visual reports (0.3.3b19)

- Introduced opt-in **temporary write/restore** capacity-authenticity spot checks for externally selected USB storage in engineering/guarded builds, and regular-image fixtures for safe automated tests. A 4 KiB preimage is durably journaled before each write; two matching restore reads are required; an unverified restore stops all further writes and preserves the recovery journal. **Spoofed-capacity controllers can still overwrite untested locations.**
- Added an original offline HTML evidence report: declared capacity, observed coverage, sampled-address heatmap, read/write latency distributions, per-position results and plain-language next steps. Sparse samples never masquerade as continuous verified capacity.
- Replaced visible manual HDD maintenance levels in the Qt workstation with an evidence-aware automatic consistency budget. Write eligibility and human consent remain independent.
- The prior Tk interface remains available until its deleted-file, filesystem and other specialized workflows are feature-parity tested in Qt; this release does not remove it.
- Added fault-injection tests for corrupt reads, interrupted restores, result classification, HTML escaping and refusal to overwrite existing reports. Physical-device validation is still pending.
- Windows fix: open capacity image fixtures with ``O_BINARY`` and use the shared positional ``pwrite`` helper so probe patterns are not text-mode mangled and mocked ``os.pwrite=None`` still falls back correctly.


## Unreleased — finish landing workbench-20261118 unique commits (2026-11-19)

- Port remaining unique `workbench-20261118` commits onto `main`: read-only surface consensus recovery, `choose_speed` finished-job average fallback (fixes stale Measuring…), and Windows GUI telemetry test diagnostics (GATE-012).
- Do **not** re-apply the obsolete workstation UI megadiff from that branch; current `main` already supersedes it with b14–b18 guarded-repair / USB / statistical recovery work. Delete the stale branch after merge.
## Unreleased — surface recovery: consensus rereads, zone baselines, sector drilldown (2026-11-19)

- Add read-only `surface_recovery` primitives modelled on publicly documented SpinRite behaviour (independent implementation, no proprietary code): majority consensus across rereads with varied read starts/head offsets, per-zone adaptive latency baselines, and bounded sector-level drilldown inside a failed chunk.
- Triage results gain `consensus_candidates`, `sector_drilldown`, `sector_probe_reads`, and `marginal_probes`. Disagreement remains reported as UNKNOWN bytes: a majority is a candidate only and is never auto-written.
- Sector drilldown runs only on non-aborted scans, is budgeted in sectors and seconds, and issues reads only. Verified read-back refresh remains the sole write path.

## Unreleased — 2026-11-19 product README, USB flash acknowledgement and SMART discovery (0.3.3b18)

- Rewrite the top-level README as a product guide with setup, workspaces, file rescue, hardware requirements, boot USB, safety boundaries and troubleshooting; move previous verbose README notes to `docs/README_ENGINEERING_HISTORY.md`.
- Add an explicit three-step destructive-flash readiness explanation. The USB flash button remains disabled until a target, exact typed confirmation and the previously required irreversible-data-loss checkbox are all present. Clearly distinguish boot-media flashing from imaging a patient disk. No confirmation is auto-checked.
- Improve SMART over USB detection when the default smartctl probe emits invalid JSON or an open-device error, by trying one bounded read-only SAT probe. Preserve critical warnings and only accept a valid ATA protocol + rotational declaration from SAT. An unresponsive first request is not retried.
- Add an explicit `Check HDD eligibility` button in the repair workspace, with results explaining whether SMART/rotation evidence was obtained. A Seagate model name alone is still not authorization for raw writes.
- Add offline regression tests for the updated SMART fallback and USB-flash state logic. GUI and real disk-flash/write success still require Windows hardware tests. See `docs/B18_USB_REPAIR_AND_README_QA.md`.

## Unreleased — 2026-11-19 statistical sector recovery ladder (0.3.3b18)

- Add fail-closed **statistical multi-sample recovery** with settle delays and a maintenance ladder (levels 1–5 / quick→extreme). Whole-buffer unanimous agreement remains preferred; **sector-granular majority** is allowed only at deep/extreme with high agreement thresholds. Weak votes never invent rewrite bytes.
- Wire `--maintenance-level` through `refresh-*` and `care-*`, Qt HDD maintenance workflows (default Normal/2), guided investigation’s sector-size second chance, and deeper postverify sampling on levels 4–5.
- Preserve all b16/b17 SSD / flash / unknown-USB write gates. This is **not** a SpinRite binary reverse-engineer or clone; see `docs/STATISTICAL_SECTOR_RECOVERY_B18.md`.
- Synthetic tests cover unanimous recovery, weak-majority refusal, high-confidence sector majority, and refresh integration. Hardware qualification remains outstanding.

## Unreleased — 2026-11-19 USB SMART identification and truthful preflight (0.3.3b17)

- Apply the **same physical-repair eligibility decision in every Qt build**, not only the guarded beta. The UI checks stable serial, SMART evidence and actual media suitability before launching a repair subprocess; a Seagate SMR model label alone does not authorize patient writes. When repair is ineligible, show **Rescue to image instead** rather than a clickable Start button that predictably fails after launch. The CLI/engine remains independently authoritative.
- Add **one bounded, read-only SAT (`smartctl -d sat`) fallback** for USB-attached SATA drives whose automatic SMART query omitted rotation rate. Accept the SAT result only when it actually supplies a numeric rotation-rate declaration and no command/open errors. Do not try SAT for positively identified NVMe; an unresponsive or incapable bridge remains UNKNOWN. Neither this probe nor a SMART pass certifies healthy media or authorizes writes by itself.
- Simplify empty-workspace presentation: hide the blank health gauge and manufacturer-hour comparison until relevant SMART evidence exists. Clarify the flash wizard's image label as **ISO file checked; BIOS/UEFI unverified**. Keep the destructive erase confirmation unfilled and mandatory.
- Correct misleading transient states: report device preflight as preflight (not a stalled disk read), and clear stale `Waiting on drive` indicators when the worker exits. This does not fix Windows kernel I/O cancellation.
- Add synthetic tests for verified HDD permission, SSD/unknown refusal, SATA-through-USB SMART fallback, invalid SAT status and no unnecessary NVMe SAT probe. Passing tests do NOT qualify real device rewrites, ISO boot, or native Qt rendering. See `docs/USB_REPAIR_PREFLIGHT_B17.md`.

## Unreleased — 2026-11-19 truthful partial-repair outcomes and strict SSD/USB gate (0.3.3b16)

- Fix Qt result translation: `partial_repair_unresolved_data` (nonzero exit) now shows rewritten/independently postverified bytes and unresolved scan evidence, rather than collapsing to generic `Stopped (2)`; failed read requests are NOT defective-sector counts; copied operator summaries use readable workflow names and that explicit distinction. Verification failure remains distinct from verified maintenance.
- Prevent the guarded GUI from showing 100% guided-workflow completion while final readback and SMART comparisons are pending. Keep current-phase progress separate; remove one redundant progress bar and place the action/result panel before the evidence map.
- Show the known read-only drive-inventory metadata even if optional Windows IOCTL storage inspection fails or times out. Never attribute a delayed probe result to a newly selected disk; display unavailable fields explicitly instead of a generic dialog.
- Recognize SanDisk Ultra 3D `SDSSDH3` model-family as an **advisory SSD rescue profile**, based on manufacturer documentation. This does not assert that an untrusted USB bridge identifies the actual attached hardware. Conflicting SMART and model evidence remains UNKNOWN.
- Enforce the HDD-only physical-write eligibility **in the core engine and planner for every source build**: a hardware repair requires independently confirmed rotational HDD media; unknown/flash/SSD/NVMe are not eligible for HDD-style rewrites even when unknown-health risk was acknowledged. Read-only rescue and image operations remain available.
- Add synthetic policy, model-conflict, GUI-output and Windows-metadata-fallback tests. These do not prove native Windows repair, BIOS booting, or post-repair drive reliability. See `docs/PARTIAL_REPAIR_TRUTH_AND_USB_IDENTITY_20261119.md`.

## Unreleased — 2026-11-18 evidence-driven media strategies and compact workbench (0.3.3b14)

- Tighten media classification using SMART/USB-NVMe protocol, confirmed rotation, exact-model SMR entries and explicit removable-flash evidence; NVR denotes surveillance workload, not a recording technology. Contradictory evidence stays unknown.
- Refuse generic HDD rewrite candidates for identified flash/SSD/NVMe in all builds; require SMART rotational evidence in the guarded HDD path. Preserve journal, independent identity, consent and verification gates.
- Probe SMART once per selected device using a bounded isolated Qt subprocess, with fingerprint-keyed caching; do not repeatedly hammer an unresponsive USB enclosure. Scan JSON includes media strategy provenance.
- Split Windows physical ReadFile requests to at most 1 MiB while preserving logically larger scan windows and 10% quick sampling. Lazily split suspect read ranges into at most 64 KiB per investigation request without allocating massive pending lists. These do not guarantee cancellation of kernel I/O.
- Compact the workbench KPI/progress layout, eliminate oversized blank drive/workflow cards, and add a vector media-policy decision ribbon. Native Qt hardware/visual testing remains outstanding. See `docs/MEDIA_AWARE_WORKSTATION_B14.md`.
- No artificial neural restoration, hardware lifespan prediction, Windows driver fix, compiled Rust raw backend, or qualified boot image is claimed.

## Unreleased — 2026-11-18 recovery USB first-run UX, sponsor link and repair preflight

- Consolidate the primary Qt sidebar to **Create recovery USB**. Select an existing local DriveRepair hybrid ISO automatically (previously selected first, then application `images/`, local `dist-live/` and other DriveRepair-named images); keep a manual override. No automatic internet fetch and no fallback to an unrelated image.
- When no ISO exists, show a clear distinction between **Use existing ISO**, **Build ISO (Linux)** and **Export build kit**. A ZIP or unbuilt recipe is never advertised as a bootable ISO. An optional `scripts/build_desktop.py --recovery-iso ...` release flag stages a real ISO next to the application and writes a SHA-256 sidecar; markers/checksums do not prove bootability.
- Add a **Support DriveRepair** link to the verified CommsTech GitHub Sponsors page and a `.github/FUNDING.yml` repository sponsor button. No automatic network communication.
- Prevent beginning an experimental physical repair in Qt when external-disk discovery reports no serial; provide a route to read-only diagnosis/rescue instead of scanning for hours and failing the identity gate afterward. Keep all CLI identity/SMART/lock/journal protections unchanged.
- Add local ISO discovery and preflight regression tests, plus an O(1) sequential extent-aggregation fast path in the evidence map (same byte-exact union semantics). Does not claim that Windows kernel-blocked I/O is fixed or that physical media was repaired. Real bootable ISO and Windows USB hardware tests still required.

## Unreleased — 2026-11-18 USB recovery-media flashing (hardware QA pending)

- Add **Flash bootable USB** to the primary Qt workstation. Selecting an ISO, a specific USB whole disk, typing `ERASE <device-id>` and acknowledging permanent data loss are separate required steps. A final destructive confirmation is also required before launch.
- Expose `flash-usb` CLI with the same destructive identity/approval gates, full image write, sector-aligned padding, flush and complete SHA-256 readback. Report byte-verified / boot-not-tested rather than treating writes as proof that a computer can boot the result.
- Reject non-USB targets, missing/changed serial or fingerprint, system/boot drives through the Windows `Get-Disk` gate, mounted Linux media, insufficient capacity, source images on the selected USB, and malformed non-hybrid ISO markers. Windows uses guarded exclusive volume lock/dismount; Linux requires root and verifies mounts/holders before exclusive opening.
- Add cooperative stop checkpoints between flash reads/writes, explicit incomplete-media errors, and synthetic short-write, mismatched-readback and stop tests. No drive is touched by the test suite.
- **Native Windows USB flashing, Linux raw-device flashing and BIOS/UEFI boot are not yet hardware-tested.** Windows USB bridges can deny raw writes or hold disk I/O despite attempts to acquire locks; report this rather than bypassing the OS. See `docs/USB_FLASH_HARDWARE_QA_20261118.md`.

## Unreleased — workbench-20261118 hardening merge and qtgui lint cleanup (2026-11-18)

- Port unique `workbench-20261118` repair-engine hardening onto current `main` without regressing guarded-repair / recovery-workbench features already landed via PRs #178–#183.
- Initialize triage `extra_suspect_reads` before optional follow-up so aborted scans still return a stable evidence result.
- Validate interrupted refresh journal transaction coordinates (alignment, bounds, digest, cursor/queue match) before any resume write.
- Expand `BrokenPipeError`/`OSError` handling in the refresh dashboard stream flush; expand one-line colon statements in `qtgui.py` (ruff E701 / issues #179–#181).

## Unreleased — multi-drive, condition evidence, live ISO and truthful Qt telemetry (2026-11-18)

- Preserve aggregated successful and failed read spans across throttled progress messages, addressing the inaccurate GUI coverage map in the supplied Windows screenshots. Keep unobserved drive regions unknown.
- Refine the Qt workstation with transparent labels, KPI tiles, higher-resolution 64×12 media visualization, improved throughput graph, phase-versus-job progress copy, a condition evidence gauge and operator-entered, documented model service-hours rating.
- Add read-only, sequential **multi-device image rescue** with per-disk fingerprint checks, distinct unused image names, storage-capacity preflight, local durable batch manifest and append-only event log. Each CLI child still performs authoritative destination ancestry and identity checks; no unattended physical writes.
- Add a 3-minute read-only diagnostic stalled-I/O watchdog and 4-minute queued-rescue timeout for isolating blocked child operations. Restrict Windows external-USB guided requests to at most 1 MiB to reduce prolonged-blocking risk. These are **not** OS-driver hard timeouts or guarantees of safe USB cancellation.
- Expose Debian live-ISO build-kit export and optional Linux-root ISO builder from the Qt GUI; include PySide6 packages. Allow explicitly opted-in offline Linux internal-disk read-only rescue. **No USB flasher or boot certification is claimed.**
- Include SMART/NVMe-based evidence index with UNKNOWN for missing/coarse telemetry, before/after condition comparison, confidence, available drive hours and optional documented rated hours. No predictive failure percentage, neural restoration, or claimed lifespan improvement.
- Add synthetic regression tests and Windows/hardware/ISO handoff in `docs/MULTIDRIVE_CONDITION_AND_LIVE_UI_20261118.md`. Native PySide6 GUI interaction, hardware writes, boot image and Rust compilation remain untested here.

## Unreleased — guarded HDD repair beta and independent post-write verification (2026-11-18)

- Add separate `--repair-beta` build with actual guarded `care-external` raw-disk write path, while preserving the original image-first public package. Reject unqualified direct raw-refresh commands in this artifact.
- Introduce evidence-based media decision logic: actual SMART + verified HDD identification for journaled refresh; SSD/NVMe, unknown medium, unsafe temperature, critical SMART and transport warnings block generic HDD rewrites. Explicit SMART warning approval remains required.
- Require separate durable disk journaling, at most 16 bounded repair regions, no inferred recording override or neighboring writes in the guarded channel. The Qt workflow now asks the operator for data-loss and SMART-warning consent rather than supplying some risk acknowledgements without an explicit prompt.
- Persist the SHA-256 digest of the prewrite bytes at each targeted transaction commit, and perform a second read-only reopening check with two fresh reads after writer handles close. Errors or mismatched bytes downgrade completion status; unreadable data is never invented.
- Compare available SMART counters before and after writes; report deterioration separately from immediate data readability. Add media policy, crash-safe digest journal, postverification, and health-delta regression tests and an image-only targeted-write smoke test.
- **No hardware success or learned neural reconstruction is claimed.** Rust image-only core is unchanged because Cargo was not installed in the review environment; Rust physical I/O migration and native platform tests remain mandatory before public qualification. See `docs/REPAIR_BETA_ENGINEERING_20261118.md`.

## Unreleased — workstation UI decision-first redesign (2026-11-18)

- Redesign the primary Qt workstation with a compact navigation sidebar, searchable `Ctrl+K` operation switcher, persistent safe Start/Stop dock, read-only/write-risk indicator, and clear per-operation readiness messaging.
- Separate measured full-drive read coverage from planned operation progress and rescue-map state; add a measured throughput trace without a remote charting dependency.
- Show source-image rescue without requiring a physical drive selection, keep actions disabled when necessary prerequisites are missing, and preserve active-job target selection against accidental navigation.
- Add evidence-focused next steps and a user-triggered local operator summary. Align the legacy Tk palette without replacing its established workflows.
- Add Qt-free presentation/gating tests and a Windows/Qt accessibility + safety handoff. **This release changes desktop presentation only**, not recovery, neural reconstruction, or physical-device write behavior.

## Unreleased — Qt workstation and evidence-driven rescue refinement (2026-11-18)

- The **Rescue data** goal defaults to copying a selected external drive to a new,
  separate image with explicit read-risk confirmation. Image-to-image rescue is
  retained as a second operation; public builds still block in-place writes.
- Refresh the Qt workstation's three-stage hierarchy, scrollable sizing,
  active goal selection, focus/accessibility styling, journal-driven progress,
  copy-throughput counters, and coarse rescued/missing/unknown map. No invented
  physical-sector health claims or false retry-pass 100%.
- Targeted rescue retry now isolates failing chunk requests into logical-sector
  ranges; allows 0–2 additional bounded attempts per failing sector; requires
  two identical reads to accept data newly recovered during retry; otherwise
  leaves an unresolved hole in the persistent map. No neural model or synthetic
  sector bytes are supplied.
- Explicitly prioritize repeatable recovered read-error candidates and then
  worst observed slow regions when limiting an experimental targeted rewrite
  batch. Final queue retains offset order; independent read/lock/identity and
  journaling rules are unchanged.
- Add fault-injection regressions for transient failures, disagreeing sector
  reads, finite retry counts, retry phase percentage and selection priority.
  No physical disk read/write validation is claimed.

## Unreleased — post-0.3.3b13 image-first beta hardening (2026-11-02)

These changes are made against the supplied 0.3.3b13 archive. **No new public version number, git tag, signed installer, or hardware qualification is claimed.** Historical release entries below are retained.

### Safety, correctness and recovery

- Add an explicitly selectable `--public-beta` zipapp build which embeds a **non-overridable distribution policy** blocking `care-image`, `refresh-image`, `care-external`, `refresh-external`, `refresh-system`, and `optimize-volume --execute` before any device access; the underlying image and physical-device writer constructors also deny access inside the public package. Engineering source and standard packages remain experimental and are **not** the public distribution.
- Change Windows coarse `HealthStatus=Healthy` mapping from an implied media `OK` to `UNKNOWN` when SMART attributes are unavailable; actual reported failure/warnings remain visible.
- Fix stale scan-checkpoint staging files blocking later saves by using uniquely named, fsynced temporary files and an atomic replace. Reject unaligned ranges in untrusted checkpoints.
- Match documented SMR drive model part numbers at token boundaries rather than accepting arbitrary model-name prefixes; preserve conservative UNKNOWN for unidentified media.
- Report refresh journal recovery capability separately: committed-boundary resume, in-flight crash restoration, and durable preimage. Hybrid/RAM backends must not be represented as crash-safe.
- Add cooperative STOP support to `refresh-image`, `refresh-external` and `refresh-system`, honored only at the existing journal-safe transaction boundaries. Legacy Tk Stop and both GUIs' close actions no longer forcibly terminate active in-place writes.

### Performance, UX and release quality

- Maintain sorted, disjoint map intervals and cache exact covered bytes, avoiding repeated full interval sorting and recalculation during GUI redraws. No patient scan speedup or I/O improvement is claimed without hardware benchmarks.
- Clarify read-only vs experimental write options in Qt/Tk and disable the Fix goal in the image-first public zipapp; present the build channel explicitly.
- Add synthetic regression tests for the build policy, checkpoint interruption recovery, media classification, progress invariants, and stop control wiring.
- Update canonical release status, public beta gates, README, desktop documentation, security policy and CI with explicit package deny-path checks. Retain historical engineering notes.

### Unverified release gates

Native Qt/Tk clickthrough and inaccessible-partition behavior on Windows, macOS discovery/safe read operations, physical HDD/SSD/SMR writes, USB unplug/power-loss, block-level lock/identity races, independent file-recovery corpora, Rust compilation/OS parity and competitor speed benchmarks require separate evidence. The image-first zipapp is a **candidate for review**, not an already-approved release.

---

## 0.3.3b13 — Windows inaccessible partitions and cooperative read-only Stop

- Preserve structured scan evidence when repair cannot exclusively lock Windows partition volumes.
- Refuse Windows writes when any enumerated partition lacks a lockable volume handle.
- Support cooperative STOP for read-only Qt scans; give truthful forced-stop reporting.
- Add synthetic regression tests and Windows operator documentation.

## 0.3.3b12 — Bounded investigation, safe Stop and truthful workflow progress

This is a **private engineering build**, not a production write-safety certificate.

- Fix the retry-budget defect: every attempted read, including each failed or
  timed-out request, now consumes the bounded follow-up budget **before** I/O.
  Failed subregions cannot trigger an effectively unbounded recursive probe tree.
  A wall-clock time budget is best-effort only: Windows/USB drivers may block a
  synchronous read beyond it; software cannot reliably cancel that kernel I/O.
- Emit structured investigation telemetry with LBA byte offset, request length,
  attempted-read count, read state, error count, and duration. Qt debug mode saves
  throttled `IO_TELEMETRY` lines to distinguish a blocked read from GUI lag.
- Guided Fix jobs accept a private `STOP` command on stdin. Scans stop at a
  read boundary, and rolling-journal writes stop **between** committed
  transactions. No in-flight rewrite is intentionally interrupted by Stop.
  Read-only jobs can be terminated, with forced exit after a short grace period.
- Qt shows separate **current-phase progress** and **estimated whole-job
  progress**; the latter is explicitly approximate until the repair plan exists.
  Investigation includes a read-attempt budget. The stalled-I/O status displays
  last offset, request size, and seconds without a result.
- Present advisory media-profile identification in the drive card. SMR rewrite
  transactions are capped at 256 KiB and at most 16 regions per guided batch;
  reported SSD/NVMe profiles cap individual transactions at 128 KiB and batches
  at 16. These are logical sizes, not HDD physical-zone or SSD NAND geometry.
  Adjacent rewrite authorization remains restricted to verified CMR.

**Known limitations:** Selected-disk `Get-Disk` timeouts on the Windows USB
bridge remain a write blocker. The native Windows Qt interface, actual USB
faults and physical writes have not been hardware-qualified here. No arbitrary
firmware writes, true physical-sector resurfacing, or AI-generated data repair.
See `docs/BOUNDED_IO_AND_SAFE_STOP_0.3.3b12.md` for operational notes.

### 0.3.3b11 — Mounted volume preparation and fault-boundary investigation

- Qt Fix workflows may explicitly authorize temporary Windows exclusive lock/dismount of mounted external volumes after scanning. Busy volumes, unknown mount paths and failed locks stop safely; no forceful dismount or permanent drive-letter removal.
- Windows raw-drive handle opening occurs only after the relevant filesystem volumes are exclusively locked; all locks are closed on failure or completion.
- Added read-only, two-sided, bounded neighboring probes around failed requests; reports observations separately from verified repair candidates.
- Reduced additional suspect rereads on failing devices and preserved unresolved error-state reporting.
- Qt error panel now explains busy-volume lock failures instead of only showing an exit code.
- Added synthetic regression tests, retaining native Windows USB hardware, PySide6 clickthrough and crash/power interruption as explicit release blockers.

### 0.3.3b10 — Full-drive Qt accuracy, contextual help, inspection and reconnect

- Fixed Qt quick-scan percentage and added ETA.
- Corrected full-drive surface map to show fractional uniquely read coverage and failure markers.
- Distributed 10% Quick Scan samples across full disk in randomized, seek-bounded groups.
- Simplified Qt goal menus; added help icons and read-only OS drive details.
- Added opt-in read-only automatic reconnect/resume using a saved scan checkpoint and identity recheck; no automatic patient writes.
- Added read-only Windows native storage property diagnostics, Linux sysfs/macOS diskutil inspection, and Rust vendor identification scaffold with no firmware commands.
- Kept PowerShell `Get-Disk` write authorization and all remaining physical hardware qualification gates.

## 0.3.3b8 (2026-11-02) — Media-aware guided scanning

- Exact-model SMR classification (Seagate ST1000LM048), conservative unknown profiles, NVMe/SSD distinctions.
- Quick Repair 10% unique-address coverage with bounded stratified random sampling, per-hardware-session recorded seeds, honest coverage metadata.
- Measured early-read transfer-size calibration and full-scan adaptive growth/shrink; 1117 deferred retries remain separate from source writes.
- Bounded read-only left/right inspection of eligible repair regions; optional CMR-only advanced neighbor rewrites after independent repeated reads.
- Smaller targeted rewrite extents than the large scan chunks; no raw-drive writes permitted by these profiles alone.
- Selected-disk Windows Get-Disk query to reduce whole-enumeration timeouts; retain identity fail-closed behavior and scan results if recheck fails.
- GUI media information, simple-by-default settings, explicit Start job and conditional dependency-install button.
- Expanded synthetic regression suite. **No Windows USB-dock, flash, firmware or boot-hardware validation.**

## 0.3.3b7 — Adaptive I/O, error continuation, staged UI and dependency readiness

- Full scans adapt read sizes (bounded to 8 MiB); Windows native I/O error 1117 is differentiated from invalid requests.
- Read-only first pass preserves good progress after isolated failures; difficult regions receive limited deferred, smaller reads. Unscanned/skipped areas remain UNKNOWN.
- Guided repair can select a bounded PARTIAL group of safe candidates when more exist, never silently completing the whole disk.
- Optional local-only anomaly history (offsets, no bytes or raw serials) helps future quick scans recheck previously weak ranges. No history in RAM-only no-file mode.
- GUI workflow buttons stage jobs; bottom Start job/Stop job executes and cancels explicitly.
- Startup prerequisites and user-approved WinGet install for smartmontools, improved scrollbars, power-mode disclosure and health display.
- See docs/ADAPTIVE_SCANNING_AND_SETUP.md; synthetic verification only, hardware certification pending.

## 0.3.3b6 — Targeted I/O investigation, firmware inventory, conservative optimization and preferences

- Added read-only bounded `probe-region` for previously failed offsets; tracks `errno`/`winerror`, subdivides rejected large requests and never writes. Error 22 is a request/access classification, not automatically a defective LBA.
- Added `firmware-info` inventory of installed revision when available, without implying the revision is current or attempting firmware flashes.
- Added Windows `optimize-volume` advisory mode. A separately authorized native HDD defrag/SSD retrim requires independently acceptable SMART evidence, exact volume mapping and current disk fingerprint. Unknown/degraded patient media are blocked.
- GUI offers firmware info, optimization advice, and failed-offset investigation without extra scripts.
- User preferences remember non-sensitive journal choice, repair policy, and dashboard visibility; new installs default to durable disk journal. Authorization/identity is not persisted.
- Updated portable-package smoke job version and new guidance. No claims of physical platter smoothing, native firmware repair or certified live-drive writes.

## 0.3.3b5 — Bounded error investigation, scan metrics and clear color legend (engineering candidate)

- **Error-limit continuation:** A Quick/Full guided repair that encounters the default 16 read-error safety limit can investigate the known failed offsets and may still refresh independent, consistently readable candidates. The remainder of the disk is explicitly *unscanned/unknown*. Read-only diagnostic scans still stop at their error budget; they do not write.
- Repeated-read disagreement or failed follow-up checks quarantine *only their known ranges*, not all other candidates. Failures without usable offsets, USB disconnect/access loss, actual critical SMART reports, and identity instability continue to block unsafe writes.
- Read errors alone now produce a media **WATCH/WARN** indicator, not a fabricated diagnosis of motor/mechanical failure or USB cable failure. Hardware/transport causality remains unknown until independently established.
- The GUI distinguishes partial, recovery-needed, and successful targeted-refresh results instead of showing a generic exit-code failure for a known safety stop. Synthetic regression checks cover limited scans, mixed good/bad regions, disconnection, UI metric cards, and no silent full-disk success.

- Guided Quick/Full repair no longer treats every isolated read error as a global write veto. Error-bearing chunks receive bounded, read-only split/retry investigation; only byte-for-byte repeatable returned data can become a candidate for another, separately journaled read/rewritten/read-back verification. Unreadable or inconsistent subregions are not overwritten.
- Added `--repair-policy preserve|balanced`. Preserve refreshes consistently readable slow regions only; balanced also considers consistently recovered error subregions. If some regions are still unknown, a partial result is explicitly reported as non-success. Destructive zero reinitialization of unreadable bytes is NOT automated.
- Critical SMART failure, unstable transport, unidentified error offsets, changing device identity, and mounted/in-use patient remain write blockers. SMART WARN requires an additional `--ack-media-warning` acknowledgment; this is NOT a hardware qualification.
- Both standalone scan and Quick/Full repair now send actual attempted/readable byte metrics, error totals, throughput, and per-operation ETA; the GUI shows scanned bytes instead of falsely counting them as rewritten. Refresh progress includes rewritten/verified bytes, speed and ETA.
- Added a colored swatch legend (pending, readable, in progress, slow, investigate, unreadable) matching the actual disk map; updated GUI warnings and progress states.
- Added synthetic read error/budget tests, full Tk swatch and metric tests. No physical disk writes were performed. Hardware testing, raw writes, rust compilation and boot tests remain release gates.

## 0.3.3b4 — Direct repair / volatile RAM-only prototype

- Added a visible no-image **Quick repair / Full repair** workflow with a
  temporary-storage choice on the main drive page.
- Process-memory journal now saves **no filesystem files or metadata** and is
  never resumable after process exit. Requires extra explicit risk acceptance
  for physical disk use; disk journaling remains the safer choice.
- Added immediate best-effort rollback on volatile write failure and critical
  fail-closed status if a restore cannot be verified.
- Advanced In-place refresh GUI supports process RAM-only, including Windows
  and Linux, subject to offline patient and exclusive lock requirements.
- Added synthetic regression, no-journal-artifact, damaged-write and real Tk
  interface tests. Hardware release gating unchanged.

## 0.3.3b3 — Guided GUI clickability and portable recovery hotfix (2026-11-01)

- Fixed all seven Start Here buttons: Notebook.select now receives its owned
  tab container instead of a nested Canvas child (previously threw TclError).
- Hid the idle dashboard to make all seven guided choices visible; kept
  dashboard toggle, automatic display while a job runs, and persistent Stop.
- Exposed the guarded Windows external-device rescue command through the GUI
  (previously mislabeled and blocked as Linux-only); still requires separate
  destination, elevated access, user risk acknowledgement, and physical QA.
- Fixed portable .pyz GUI subprocess invocation: child jobs re-enter the .pyz
  instead of relying on an installed `driverepair_desktop` module.
- Exposed unexpected GUI callback exceptions to users and the bounded log.
- Set child progress streams to UTF-8 and closed their pipes after completion.
- Added real Tk GUI button, tab, visible-control and image-rescue regression
  tests with no physical-disk access; CI adds Linux Xvfb GUI validation.
- Aligned Python desktop packaging version and zipapp build versions.
- No new physical-drive recovery / write capability; public hardware beta
  validation remains outstanding.

## 0.3.3b2 — Journal-backed rescue status and lab safety hotfix (experimental)

- Added OS-held exclusive writer lock across forward and retry passes; simultaneous jobs against one image/map are rejected while monitoring remains read-only.
- Added read-only `rescue-status --output IMAGE --json`: verifies recovery journal accounting and reports committed cursor, missing/unprocessed regions, and clean first-pass completion. **Image file length is never a completion signal.**
- Removed silent automatic `refresh-external` calls from Windows acquisition/resume/watch scripts; destructive media maintenance must be a separate authorized workflow.
- Replaced forced process killing and stale hard-coded patient/destination defaults with explicit operator choices; watcher reads journals only and manual resume uses structured progress.
- Separated script JSON results from diagnostic logs; added synthetic regression tests for sparse preallocation, invalid/missing maps and lab-script safety.
- These changes do not prove raw-device data correctness, cross-platform hardware support, or external-drive write safety.

## 0.3.3b1 — Integrity-aware image recovery (experimental)

- Added per-chunk SHA-256 reference baselines, image audits, and only-if-reference-matches restoration into a NEW image.
- Incomplete/unknown rescue ranges are not mislabeled bit flips.
- Added bounded optional repeat reads of suspicious triage regions to detect inconsistent OS-returned bytes.
- Added GUI integrity page and safety/trust documentation.
- Added optional Linux copy-on-write reflink optimization for new corrected images, with streaming fallback and output readback; existing images remain untouched.
- Kept raw-device write behavior unchanged; no new hardware repair claims.

## 0.3.2b1 — 2026-11-01 — Professional recovery dashboard (engineering candidate)

- Replaced repeated `RESCUE cursor=...` log spam with compact terminal progress
  and structured, throttled JSONL events for the GUI; machine-readable final
  JSON remains on stdout.
- Recovery dashboard: committed rescue data, unreadable bytes/regions, status,
  current speed, forward-pass ETA, destination free space and a bounded sector
  activity map. Unscanned regions are never colored as healthy.
- Integrated image/external/offline-system rescue GUI progress; rescued-data
  visualizations do not claim cryptographic correctness or physical health.
- Added **Resume**, **Retry gaps**, explicit **Save report** and **Open
  destination** controls. Technical logs remain available but hidden by
  default; bounded the log buffer for long-running work.
- Fixed progress-bar layout, made individual workflow pages scrollable on
  laptop screens, and kept the Stop control visible at the bottom.
- Added synthetic telemetry/CLI tests and virtual-display GUI end-to-end
  smoke test; production drive hardware not touched.
- Release remains NOT CLEARED for unattended patient writes, unverified
  BIOS/UEFI boot media or claims of superiority to competing software.

## 0.3.1b1 — 2026-11-01 — Last-resort + offline recovery (NOT RELEASE-CLEARED)

- Last-resort Linux `refresh-system`: experimental Adaptive in-place refresh of an
  unmounted internal disk with a verified RAM journal and multi-ack gates.
  Protects only the active chunk; not a backup; Windows/macOS system refresh remains unsupported.
- Windows live `rescue-external` / monitor history now use PhysicalDrive vs
  destination drive-letter disk-number isolation (previously Linux-only fail-closed).
- Added Linux internal whole-disk inventory (`list-all-linux`), explicitly
  offline read-only `rescue-system`, and `plan-system-recovery` preflight.
- Allows verified mounted network destinations (NFS/NFS4/CIFS/SMB3/SSHFS) for
  imaging where local source/destination block ancestry cannot apply.
- New guided GUI **Recover OS drive** workflow; original external-only
  desktop device view stays unchanged.
- Fixed the offline rescue post-read identity check to reselect from the
  internal-disk inventory rather than incorrectly requiring an external disk.
- SMART monitor now alerts on a first nonzero fault-counter baseline; Linux
  monitor state preflights destination ancestry. GUI initializes sensor health
  as UNKNOWN until diagnostics actually run.
- Added a non-destructive Debian live-build ISO recipe plus structural ISO
  catalog checker; **no ISO was built or boot-tested in this environment**.
- Updated one-drive recovery, trust, boot, security and beta release docs.
- Synthetic tests/portable packaging run; native Rust and real hardware
  operation remain unproven until CI and independent validation.

## 0.3.0b1 — 2026-11-01 (controlled engineering candidate)

- Read-only deleted FAT32 candidate catalog with stable selection IDs, selected-only restore and revalidation.
- Optional Sleuth Kit `fls`/`icat` deleted-file preview/selected extraction for additional filesystems (installation dependent).
- Guided GUI Start Here workflow and multi-select deleted-file table with filesystem backend chooser.
- Bounded deterministic stratified quick triage sampling with neighboring suspect region investigation; never certifies unsampled areas.
- Python image-rescue `--multi-pass` to perform first-pass salvage and targeted retries in one operation.
- Standalone `rust/recovery-core` no-dependency regular-image multipass rescue crate (compiler/CI validation pending).
- Scheduled read-only drive-health trend monitor (SMART/NVMe and optional sampled triage); no automatic patient rewrites.
- Privacy-minimized SHA-256 evidence-image manifest without unsupported chain-of-custody claims.
- Multi-FS detection + `recover-image` (FAT32/NTFS/exFAT undelete; Btrfs/ZFS/APFS/ext → RAW carve) with expanded carve formats.
- Soft mechanical indicators on refresh: `--acoustic-watch`, `--shock-guard`, `--smart-deltas` (WATCH/STOP only; latency/SMART remain primary; not platter metrology).
- Updated guides, benchmark plan and honest public-beta safety gates; original bootloader sources preserved as experimental.

## 0.2.9b1 — Public-beta candidate safety and throughput groundwork (2026-11-01)

- Repository Detective export `findings-20261101T180217Z.json`: DriveRepair open findings remediated (ambiguous loop names, unused imports, Rust retry sleep wired, recovery retry settle delay, opaque test tokens). Mixed-repo nettech/RD rows were not in scope. See `docs/FINDINGS_REMEDIATION_20261101.md`.
- Live lab: third SanDisk SDSSDH3 500 G Adaptive with `--confirm-identity` completed; identical-rewrite probe OK (contrasts prior units’ WinError 1117/121).
- Disk enumeration now reports a 12-character patient fingerprint, location hint (when supplied by OS), capacity, model, bus, and masked serial. Raw writes require the matching `--confirm-identity` fingerprint; duplicate USB-bridge serials are blocked.
- Windows discovery now prefers Get-Disk (boot/system metadata) rather than WMI; legacy-only enumeration cannot authorize destructive refresh. Fixed a previously failing cross-platform mock.
- Added **opt-in Linux RAM-filesystem journal** (`ramdisk`). The active original bytes and metadata are written to a verified tmpfs/ramfs, not unprotected Python heap, with swap fail-closed, local USB-connected NUT UPS or laptop battery checks, and power rechecks before every write. Requires `--ack-volatile-journal`, `--ack-dock-power-backed`, and the usual destructive acknowledgements. Does NOT survive host power loss/reboot and cannot prove the dock is actually UPS-backed.
- Added read-only `ram-journal-check` command and GUI selection for disk vs RAM journal with extra warnings.
- Increased selectable refresh and rescue chunk sizes up to 64 MiB for lab benchmarking; larger chunks trade more in-flight exposure for fewer syncs. GUI offers configurable chunk size, default 8 MiB.
- Eliminated eager construction of all image rescue jobs: sparse 12 TB images now start in bounded memory. Fixed recursive Linux holder checks for active partitions.
- New RAM-policy, interrupted-write, 12 TB sparse image tests. Baseline 98 tests included one previously failing Windows device discovery test; updated suite includes 105 tests (one platform skip on Linux).
- Desktop build and CI portable-archive smoke check updated. Rust boot prototype remains experimental and is not used in the desktop I/O implementation.
- No physical devices or UPS were tested. Public beta remains blocked pending real hardware, platform, and competitive benchmarks.

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

### Experimental follow-up — one-drive in-place refresh

- Added `refresh-system` for explicitly consented, OFFLINE internal disk refresh
  from trusted Linux live media, reusing the existing transactional media engine.
- Added no-image last-resort path in the Recover OS drive GUI, with exact device
  identity confirmation and explicit warnings about volatile data loss.
- Requires approved RAM filesystem and live UPS/battery checks for volatile
  journaling. Internal disk mode no longer conflates USB-dock power confirmation
  with an internal SATA disk; USB bridges still require the separate acknowledgment.
- Added synthetic CLI safety-path tests. No physical device testing or
  manufacturer firmware remapping validation has been performed.

### 0.3.3b9 — Qt workstation migration and resumable read-only scans
- Optional PySide6 workstation with staged Start, drive choices, interactive sampled activity map, advanced log, and clear high-risk write confirmation. Existing Tk specialist tools remain.
- Five-second recent throughput and separate job average; fixed misleading “current speed” label.
- Private, identity-bound full-scan checkpoints permit explicit read-only resumption after unplug/reconnect; 433/no-device classified as access failure.
- RAM-only guided writes keep their no-file default; scan checkpoint is a separate explicit opt-in.
- This does **not** add raw firmware vendor commands, AI-invented evidence, or automatic physical-write resumption.
