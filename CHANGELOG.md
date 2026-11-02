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

# Changelog

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
