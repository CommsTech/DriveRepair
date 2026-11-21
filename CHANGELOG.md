# Changelog

## 0.3.3b36 — 2026-11-21: Evidence-first agent QA and release gates (engineering source)

- Added Gitea release-hygiene CI and clean-source packaging checks; active docs and executable version metadata now agree. No missing platform job can count as success.
- Added explicit native Windows Qt and real QEMU BIOS/UEFI qualification workflow, separate from Ubuntu CI. The QEMU test has no attached disk, checks guest GUI launch over serial, and writes per-firmware evidence and ISO SHA-256. Hardware boot remains NOT_PROVEN until run.
- Propagated DriveRepair GRUB menu configuration to both live-build BIOS and UEFI recipe directories, and synchronized portable boot-kit assets. Structural ISO checks require xorriso; firmware and physical boot still require real tests.
- Added opt-in Windows USB dock SMART QA results using `/dev/pdN`, without storing full serial numbers or granting repair authorization.
- Eliminated numerical scoring of uncalibrated vendor ATA 187 raw counters; an isolated warning cannot imply either 82/100 or 100/100 drive reliability.
- Added independent artifact-bound promotion evidence validation, short agent navigation and reviewer guidance, and native Qt synthetic SSD/HDD route regression tests.
- **Code-review follow-up:** qualification Qt missing-window is a hard fail (not a green skip); Windows job installs `desktop[qt]` and rejects skipped essential tests; VM evidence uploads on success/failure; release hygiene supports Python 3.10; readiness hashing rejects non-regular files; QA SMART unverified fails the sweep; ATA 5/197/198/199 positives require model thresholds; Ruff/Bandit cover `scripts/`.
- **No real HP boot or Windows dock writes were performed.** The project is not hardware-qualified for public physical repair.


## 0.3.3b35 — 2026-11-20: Live session/Windows repair routing and archive verification UX (experimental)

- Added DriveRepair-branded GRUB menu for normal graphical live boot, `nomodeset` compatibility graphics, and text-only troubleshooting, using live-build's resolved kernel/initrd paths. No OS installer entry. This is a RECIPE ONLY until a rebuilt ISO passes physical BIOS/UEFI and HP tests.
- Configured live user `driverepair`, LightDM graphical autologin and Xfce Qt app autostart; documented expected Debian Live fallback credentials (`driverepair` / `live`), pending boot verification.
- Tightened ISO structural qualification to check the actual emitted GRUB menu and reject unresolved template tokens or unbranded output. Updated both source and portable-build kit assets.
- Fixed Qt action label error for approved HDD review (`review` route had been checked against the nonexistent `repair` route).
- Removed implicit on-device CHKDSK redirection for blocked HDD techniques, including silent Windows SSD-first selection, so operator intent remains explicit. No raw-write gate was weakened.
- Corrected Windows SMART paths to smartmontools `/dev/pdN` aliases (instead of raw Win32 paths), with identity/path cross-checks, and updated all primary, SAT and SMART-log probes. This is a suspected cause of status-bit-1 failures but requires a Windows dock retest.
- Corrected SMART parse-error guidance: exit status bit 0 is smartctl CLI/device-type rejection, not proof of bridge hardware hiding SMART.
- Added read-only `inspect-windows-access` diagnostics and structured WinError 5/elevation results before Windows scans. When SMART is unavailable, DriveRepair can also report exact-disk Windows Storage reliability counters as weaker telemetry; neither path becomes a SMART pass or bypasses physical-write gates.
- Added determinate file-count progress for cold-storage baseline hashing, with fail-closed archive-list drift detection; no image or source write.
- All live boot, hardware write and Secure Boot capabilities remain unverified on target hardware.

## 0.3.3b34 — 2026-11-20: Cold-storage archive fixity and ISO-host prerequisite

- Added read-only, file-level SHA-256 baseline and periodic verification of removable photo/file archives without creating disk images. Detects changed, missing, newly added, and unreadable items. Baselines are never overwritten; output must be outside the archive.
- Added a Qt **Cold storage integrity** workflow with progress and a modern, offline HTML report. A different drive letter on reconnect is supported, and status distinguishes byte changes from intentional new files.
- Enforced no symlink traversal, immutable baseline creation, streaming bounded-memory hashing, and rejection of incomplete baselines. Added fault and tampering regression tests.
- Corrected Debian WSL ISO-build prerequisites to include host-side `python3`, which the structural validator requires. The November 20 debug log showed the build reached ISO generation but failed at validation because `python3` was absent. Bootability still requires actual BIOS/UEFI tests.
- Source-only and synthetic tests do not prove the GUI on Windows, physical disk repair, ISO boot, or integrity of an already-corrupt baseline.


## 0.3.3b33 — 2026-11-20: Recovery ISO visibility, sparse output, truthful repair selection

- Added a nonmodal Debian/WSL ISO-build progress window with ongoing stage messages, an indeterminate progress indicator, and a persistent full log. Distinguishes a completed image from a failed build, with WSL device-node preflight and no claim of verified BIOS/UEFI boot.
- Added an explicit System readiness action and one-time consent-based Windows SMART prerequisite notification.
- Automatically requests bounded hardware-health evidence after diagnosis, without confusing sampled read results with guaranteed hardware health.
- Removed automatic rerouting of explicitly selected HDD maintenance to a filesystem repair operation. Unsafe methods remain ineligible, but the operator is told why.
- Added optional sparse-zero rescue images to single and serial multi-source workflows: only successfully read zero-filled blocks are elided; unreadable regions remain journaled, and resume enforces consistent image policy.
- Added regression tests for sparse data accounting and policy-safe restart. Native Windows Qt, WSL bootstrap and physical-media repairs remain hardware-unverified.


## 0.3.3b32 — 2026-11-20: Repair operation selection and Windows volume binding

- Corrected the Qt repair-method selection when switching drives: a recognized SSD/flash source now displays the on-device Windows filesystem method instead of leaving an HDD targeted/full-scan rewrite selected while silently changing the Start action.
- Added an asynchronous read-only CLI volume lookup (`list-repair-volumes`), returning only NTFS/FAT/exFAT volumes whose partition DiskNumber, size, and non-system state match the selected external PhysicalDrive. A missing, RAW, or unmounted filesystem yields an explicit explanation, not a fake physical repair.
- The modifying CHKDSK `/f` worker still independently repeats device identity, external/non-system and exact partition mapping checks, requests backup and typed write consent, and never assumes that a successful command fixes underlying NAND or sectors.
- Repair workspace no longer uses the contextual assistance control to silently start image restoration.
- Added synthetic tests for wrong-disk binding, changing identity, duplicated or invalid volumes, Windows enumeration timeouts, and the Qt/CLI selection contract.
- **Qualification:** synthetic Python tests passed. Native Windows Qt, successful on-device filesystem maintenance, and physical HDD journaled repair are still unverified. The uploaded debug logs only prove read-only scans.


## 0.3.3b31 — 2026-11-20: Windows repair-lock lifetime and Debian WSL startup fixes

- **Windows raw-disk access:** after obtaining and retaining exclusive locks on every discoverable patient filesystem volume, open the physical disk using Win32 `FILE_SHARE_READ | FILE_SHARE_WRITE` rather than unnecessarily requesting an incompatible `share=0` handle. A successfully opened raw handle is not itself proof of exclusive disk access; filesystem-volume locks, external/system checks, independent identity verification, separate journal, write consent and readback remain mandatory.
- **Lock lifetime:** close the raw physical disk handle **before** releasing acquired volume handles; release in reverse acquisition order. Preserve fail-closed behavior when a volume cannot be locked, is in use, changes partition layout, or has no safe lockable handle. Mounted GUID paths cannot sidestep explicit dismount authorization.
- Improve Win32 error messages with the failed volume and operating-system error code; never use an unapproved force-dismount to bypass a lock failure.
- **WSL ISO build on Windows:** stop launching Debian merely to translate staging/output drive paths. Use a deterministic default WSL `/mnt/<drive>/` translation and verify availability inside the asynchronous build. Distinguish an absent Debian distribution from an unresponsive or uninitialized WSL installation, avoiding duplicate `wsl --install` attempts after `ERROR_ALREADY_EXISTS`.
- New fault-injection tests cover Windows CreateFile sharing, held-lock cleanup and close order, mounted GUID paths, installed/missing/unresponsive Debian cases and Windows-path mapping. Linux-hosted tests prove only the software logic; **real Windows disk locking, filesystem write, WSL ISO build, and BIOS/UEFI USB boot remain unverified.**

## 0.3.3b30 — 2026-11-20: On-device repair and Restore workspace separation

- Separated the Qt **Repair drive** and **Restore data** workspaces. SSD/flash repair actions no longer silently image drives or switch to Restore.
- Added a guarded **on-device Windows filesystem repair** route using CHKDSK `/f` on mounted NTFS, FAT and exFAT volumes. It is deliberately *logical filesystem repair*, not physical NAND rejuvenation or reconstructed unreadable sectors.
- Windows checks an independent Get-Disk external/non-system gate, re-selects the drive, confirms the volume belongs to the exact selected PhysicalDrive and has supported geometry, and requires backup affirmation and an exact typed repair consent before any write command.
- Preserved the existing independent, journaled rotational HDD repair engine. No SSD is admitted to that engine, and a filesystem repair does not bypass it.
- Updated the Qt workflow selector, risk labels, visible primary action and results. Restore remains a separate workflow. Changed the stepper graphics to reflect Diagnose, Restore and Repair separately.
- Added regression tests (including forbidden interruption of an active CHKDSK subprocess) for altered volume/disk identity, system/boot drive refusal, unsupported filesystems, missing authorizations, public-beta write denial, and actual CHKDSK invocation arguments.
- No native Windows GUI clickthrough or hardware write/boot qualification performed here. Do not market this as demonstrated physical media recovery.


## 0.3.3b29 — 2026-11-20: Repair workflow and live hardware diagnostics

- Image-first restoration can start **inside Repair & Restore**, without silently switching workspaces.
- Live ISO build adds an explicit Memtest86+ boot option, stress-ng and stressapptest, plus a bounded CPU/RAM diagnostics desktop launcher. Actual ISO build/boot remains unverified.
- Read-only Linux sysfs fallback reports disk/bridge geometry and rotational hints when SMART is unavailable; it cannot authorize in-place repair.
- Unknown/SSD media remains ineligible for generic HDD sector rewrites; journal/identity/locking controls unchanged.

## 0.3.3b28 — 2026-11-19: scan evidence durability and source hygiene audit

- **Fixed buffered telemetry loss at scan phase boundaries.** If a producer transitions directly from scanning to a terminal or verification state, pending read spans are emitted under the original SCANNING phase before the terminal event; no covered region is silently discarded. A transient progress-stream failure no longer discards buffered spans or advances the throttle clock. Progress reporting remains best-effort and cannot guarantee delivery across persistent stream failures.
- **Fixed checkpoint retry after a failed durable write.** The checkpoint throttle time is now committed only after the atomic replacement and durability checks complete. A failed replacement can be retried immediately, even within the nominal checkpoint interval.
- Added focused fault-injection regression tests for failed checkpoint replacement, transient telemetry sink failure, and SCANNING→DONE phase transitions. Preserved independent disk-write authorization and device safety checks.
- Added a deterministic, dependency-free clean-source ZIP packager (`scripts/create_clean_source_archive.py`) plus tests. Generated Rust target caches and historical nested release ZIPs had dominated the uploaded archive. No active application code or documentation is deleted from the source deliverable.
- Removed a pytest discovery warning by renaming a test fixture; no application feature was removed as "dead code" without a demonstrated unused reference.
- Verification is limited to this environment: Python synthetic suite and source-package checks. PySide6 native-Windows UI, Rust compilation, actual device-repair success, bootability, and hardware failure recovery are **NOT VERIFIED**.

## 0.3.3b27 — 2026-11-19: native read-only ATA IDENTIFY fallback (experimental)

- Added a bounded, isolated Windows SAT ATA IDENTIFY DEVICE probe for compatible USB bridges when smartctl and Windows storage-property identification are inconclusive.
- Validate the returned ATA model, full logical capacity, logical sector size, serial suffix, and rotational rate against the selected inventory record before treating it as a corroborated HDD candidate.
- Preserve unknown SMART health, independent Get-Disk system/external checks, disk-fingerprint consent, exclusive locking and durable separate-disk journal. A second ATA probe immediately before writable access rejects a changed/unavailable device.
- An SSD, missing identity, conflicting model/serial/capacity, bridge that refuses SAT, or a driver that blocks exclusive access remains ineligible for HDD rewrites. No read-only fallback can prove future drive reliability or regenerate unreadable data.
- Added synthetic regression tests for SATA/SAT pass-through encoding, valid/mismatched ATA replies, withheld SMART health, probe timeouts and guarded-beta unknown-health consent.
- Windows hardware verification of the SAT call, live disk locking, rollback, and successful physical repair is still **NOT PERFORMED**.

## 0.3.3b26 — 2026-11-19: Windows USB discovery and write-gate regression fixes

- Fixed a **real repair-blocking contradiction**: Windows inventory was changed to CIM-first, but the journal preflight still rejected every disk whose provenance wasn't literally `Get-Disk`. The journal preflight now repeats the independent authoritative `Get-Disk` external/online/non-system safety gate regardless of inventory source. This does **not** waive device serial, SMART/media policy, locking, separate journal, explicit consent, or readback requirements.
- Recognize USB-attached SCSI/UASP disks only when a separate bounded Windows native descriptor confirms USB transport, drive index, and compatible capacity. A second USB device is no longer silently hidden when a different device already advertises USB directly.
- Add a last-resort **read-only** native USB inventory when Windows CIM, WMIC and Storage cmdlets cannot discover drives. It does not fabricate serial numbers or qualify raw writes.
- Bound Qt inventory discovery and surface the actual failure/timeout instead of displaying an indefinite "Looking for external drives" placeholder. Invalid inventories clear stale drive selections safely.
- Added synthetic Windows identification, identity-conflict, and independent write-preflight regression tests. Native Windows USB behavior and real physical-drive repair remain hardware qualification items.

## 0.3.3b25 — 2026-11-19: Media-aware Repair & Restore actions

- Replaced the misleading disabled "Start authorized repair" control with a **context-aware** primary action. When the selected device is an SSD or removable flash drive, it switches to read-only image rescue instead of attempting HDD sector refresh. Unknown HDDs trigger read-only identification; corroborated HDDs retain their independent guarded rewrite checks. Switching workspaces never starts a physical write.
- Renamed the Qt repair workspace **Repair & restore**, and provided a direct specialist action for copy-only ext2/3/4 filesystem repair. The source image and original physical disk are never modified by that operation; `e2fsck` is required for ext filesystems.
- Added six regression tests validating that no SSD or unverified USB device gets write authorization from the new UI routing. All previous CLI/engine checks remain in effect.
- **Limit:** This release does not claim to resolve Windows USB raw-write access, restore SSD endurance, or qualify a specific HDD for repair. Native PySide6 and physical drive hardware still require external qualification.


## 0.3.3b24 — 2026-11-19: Windows-native identification when SMART fails

- Added a versioned, offline, source-attributed drive model catalog (`data/drive_models.json`) with four manufacturer-supported entries. Media-profile matching reads the catalog; drive-model specifications guide read policy only, never physical-write authorization. Added non-matching-model and source-provenance tests.


- **A failed smartctl/SAT query is no longer the end of identification.** The `health` command
  automatically attempts read-only `IOCTL_STORAGE_QUERY_PROPERTY` and disk-size queries in
  an isolated, nine-second Windows child process. These include reported seek penalty,
  TRIM support, model/serial suffix, transport and size. A device which omits any required
  field remains unverified; the app does not infer mechanical media from USB alone.
- **Conservative native HDD corroboration:** the manufacturer-style HDD part number must
  match the independent Windows device descriptor, exact size and reported serial suffix
  must match inventory, and the driver must report seek penalty with no TRIM. If the bridge
  contradicts itself or an SSD/flash model is selected, HDD refresh remains denied.
  These observations can still be synthesized by a USB bridge, so they are *not*
  a guarantee of physical media and do not certify any health status.
- **Unknown-health laboratory path (guarded beta only):** a corroborated HDD may proceed
  through the existing exclusive volume lock, full identity recheck, independently
  journaled bounded repair and readback flow **only if** the user additionally approves
  the `--ack-unknown-health` risk after acknowledging possible data loss. No unattended
  writes are authorized by the native media query alone. Critical failures/warnings still
  veto automatic confidence. A separate known-good data copy is strongly recommended.
- The Qt readiness action now *first probes* alternative Windows media properties even
  when SMART is missing. Missing evidence is explained; it no longer automatically sends
  everyone to smartctl installation. When native evidence is insufficient, Qt offers
  approved SMART setup (when absent) or image rescue instead of endlessly retrying.
- **Windows recovery USB setup** now offers an explicitly approved action to start Debian
  WSL installation. Administrator permission, Internet, Debian first-run setup and reboot
  can still be necessary; this does not itself create, flash, or prove a bootable ISO.
- Added tests for driver descriptor validation, misleading bridge flags, model/serial/size
  mismatches, SSD rejection, native-probe timeouts, explicit unknown-health authorization,
  and bounded repair-batch policy. These are synthetic tests, not a Windows hardware pass.

## Unreleased — 2026-11-19 known-SSD readiness stops SMART retry loops

- Known SSD/NVMe/flash model families (for example SanDisk ``SDSSDH3``) now route
  the HDD-maintenance next action to **Rescue data to an image** instead of
  endlessly offering "Check drive SMART and identity". Targeted HDD region
  rewrite remains fail-closed for flash; SMART polling cannot unlock it.
- SMART probe failures decode smartctl bits 0–2 in plain language (parse /
  open / ATA command) so USB bridge limits are clearer than ``status bits 1``.
- Ruff E701 cleanup in ``boot_validation.py`` (Gitea #207 / #208).

## 0.3.3b23 — 2026-11-19: actionable repair readiness and USB SMART evidence

- Consolidated the Qt repair preflight into one contextual action: choose a disk, enable SMART tools with consent if absent, retry read-only SMART/ATA identity, or route to image rescue. A disabled hardware-write button no longer leaves the user guessing about the next step.
- Preserve and display the real per-device SMART query error, including USB bridge/SAT failures; ignore health responses whose disk fingerprint does not match the selected disk.
- When USB smartctl autodetection supplies a rotational speed **but returns an error**, try a bounded SAT pass-through read to obtain a valid complete ATA snapshot. Never downgrade existing SMART failure warnings or treat OS HealthStatus/model names as physical-write authorization.
- Restore a single, cleaner repair context instead of multiple competing setup and help buttons. Keep the independent engine/journal/lock/identity safety checks unchanged.
- Added synthetic tests for the UI decision states, misleading partial USB SMART results, device-identity gates and flash-media inhibition. This is **not** evidence of repaired physical media.

## Unreleased — SMART breadth: full attribute table, read-only logs, more USB bridges (2026-11-19)

- Health snapshots now retain the **whole ATA attribute table** (bounded at 64)
  with normalised Value/Worst/Threshold, `when_failed`, and raw value/string,
  instead of only seven raw counters. The seven-counter subset is kept for the
  existing condition index and monitor so scoring behaviour is unchanged.
- **Self-test and error logs** are read (`smartctl -l selftest`, `-l error`) and
  summarised with entry counts and the most recent entries. Nothing is started:
  no `--test`, no `--smart`, and the notes say so.
- **USB bridge breadth**: after the plain SAT probe, up to four ordered
  device-type probes are tried (`sntasmedia`, `sntjmicron`, `sntrealtek`,
  `usbjmicron`) inside a 25 s budget and 5 s per call, so a marginal bridge sees
  a few short commands at most.
- **Deliberate restraint:** log queries are skipped when the controller already
  reports failure, and for NVMe (whose health log already carries error
  counters). A device in trouble is not sent extra commands.
- The HTML evidence report gains a **SMART evidence** section (attribute table +
  log summary) that states plainly that a normalised value near its threshold is
  not a failure prediction. The section is omitted entirely when no SMART
  evidence exists.
- 7 new tests with synthetic smartctl fixtures; `scripts/qa_install_smartctl.ps1`
  installs smartmontools through winget and captures health snapshots on Windows.

## Unreleased — specialist review pass: consensus rescue, durability cadence, security hardening (2026-11-19)

Four specialists (competitive research, performance, code quality, security)
reviewed `main` and every implemented finding below has a regression test.
Full disposition, including deliberately deferred work, is in
`docs/SPECIALIST_REVIEW_20261119.md`.

- **Rescue now uses the consensus engine it already shipped.** When the retry
  pass is about to declare a sector lost, it attempts a bounded majority vote
  across shifted rereads. Recovered sectors are recorded as
  `consensus_recovered_bytes` / `consensus_recovered_ranges` — provenance that
  never claims verified data. Disable with `consensus_attempts=0`.
- **Durability cadence:** the rescue loop validates its map at checkpoint
  boundaries instead of re-sorting it on every chunk (32 ms/call at 50k ranges),
  and adaptive scans no longer write a durable checkpoint after every chunk:
  measured **256 → 2** saves for a 256 MiB scan. Forced saves on abort and
  completion are unchanged, so resume semantics are preserved.
- **Security (both LOW, from the security review):** SMART evidence is now read
  only from the resolved `smartctl` path — never a bare PATH lookup that a
  planted binary could satisfy; and a repair journal refuses to be adopted
  through a symlink and is chmod 0700 when an existing empty directory is used.
- **Correctness:** the rescue CLI's non-JSON path printed raw JSON (no human
  output at all) and now prints a compact status line; the scanner no longer
  masks a `TypeError` raised inside a progress callback.
- **QA tooling:** `scripts/qa_readonly_triage.ps1` runs bounded read-only scans
  on Windows and `scripts/qa_summarize_results.py` summarises the results
  (handles PowerShell's UTF-16 + bracketed capture). Verified against three
  external drives: 0 read errors, spot-check coverage only, SMART UNKNOWN where
  smartmontools is absent.

## Unreleased — workstation responsiveness and first-run clarity (2026-11-19)

- **Responsiveness:** progress repaints are coalesced to a 10 Hz cadence. Phase
  changes and completion still render immediately and the newest event is always
  flushed, so a fast source can no longer flood the UI thread with thousands of
  label/map updates per second. The decision is a pure, unit-tested helper, not
  an inline timing check.
- **Disabled actions look disabled:** the primary Start button had no `:disabled`
  style and kept its teal action colour while refusing to start — the exact
  "green button that does nothing" contradiction. It now greys out, verified by
  sampling the rendered button rather than the stylesheet string.
- **No clipped labels:** the evidence tab caption is shortened to *Surface map*
  with the full meaning in its tooltip. The sidebar support button is shortened
  to *Sponsor* because Segoe UI measures the full caption at 264 px inside a
  214 px sidebar; the complete wording moves to its tooltip.
- **Empty inventory explains itself:** with no external drive the selector is
  disabled, shows a placeholder, and the note tells the user to connect the drive
  and press Refresh instead of presenting a large unexplained empty dropdown.
- **Accessibility and keyboard flow:** accessible names on the source-drive and
  operation selectors and the image-path field; `Ctrl+Enter` starts a ready job
  under exactly the same readiness gate as the button, and `F5` refreshes the
  drive inventory. Sidebar footer contrast and size raised.
- 12 new tests (7 offscreen Qt, 5 presentation) cover these behaviours; Qt tests
  skip cleanly on hosts without PySide6.

## 0.3.3b22 — 2026-11-19: SMART bridge fallback and actionable scan results

- Correct successful ATA/SAT fallback parsing for USB bridges that reject the initial query and only respond to an alternate supported bridge mode.
- Use the selected SAT bridge mode for subsequent *read-only* SMART self-test/error log requests; avoid falling back to a failed autodetection path.
- Treat completed read-only diagnostics with recorded read errors as **scan completed with findings**, even when the CLI's nonzero exit code signals those errors. Keep interrupted jobs distinct.
- Preserve the post-scan **Address scan errors** recommendation; it uses recorded failed positions and never automatically writes to the source disk.
- De-duplicate exact failed read ranges and enforce a strict maximum for follow-up work to avoid unnecessary repeated reads.
- Added synthetic regression tests. This is not a new physical repair engine, a bundled Windows smartctl binary, or a qualified boot ISO.

## 0.3.3b21 — 2026-11-19: live evidence, focused follow-up and Windows boot building

- Qt layout: remove numbered sidebar items, provide separate **Assessment** and **Surface map & throughput** tabs to reduce stacked scrolling; hide drive/workflow setup forms during active jobs and restore them at completion.
- Add `Address scan errors…`: after a read-only scan, revalidate the same device identity and geometry and reread only previously recorded failed regions. The new CLI `recheck-scan-errors` is strictly read-only, time/read-budgeted and never treats consistent bytes as repaired media.
- Add Windows Debian WSL ISO builder invoked from the recovery-USB entry. It constructs a fresh kit, copies it into WSL's Linux filesystem, optionally installs Debian build prerequisites with consent, and runs the existing live-build recipe. USB flashing remains separately authorized; actual BIOS/UEFI boot unverified.
- Add verified staged portable Windows smartctl detection and a consent-based Windows Package Manager setup action. The source repository does not ship an upstream binary; authentic release verification and GPL obligations remain release engineering tasks. USB bridge support remains hardware-dependent.
- Retain all existing physical repair gates and journal checks. This revision does not prove improved disk lifespan or resolve OS/kernel USB read stalls.
- Synthetic regression tests and Windows hardware QA checklist extended; native Windows Qt UI, real ISO boot and physical drive writes still require validation.

## 0.3.3b20 — 2026-11-19: Qt consolidation, boot-media qualification, and UI cleanup

- Remove the old Tk desktop runtime from the distributed source. Both `gui` and `qt-gui` now launch only PySide6/Qt; `gui-legacy` is a compatibility alias that also opens Qt, not Tk. Python CLI operations remain independently available.
- Add Qt **Specialist recovery tools** to expose image filesystem detection, scan, rescue/resume/retry, file carving and undelete (including Sleuth Kit), ZIP salvage, hash integrity auditing and restore-from-reference, clone-only ext filesystem repair and evidence export.
- Add **Hardware diagnostics** for read-only firmware/capability inspection, sampled benchmarks, bounded failed-offset rereads, and Windows volume optimization *advice only*; potentially stressful reads require explicit approval.
- Remove empty, misleading dashboard data until real job evidence arrives; show an actionable HDD eligibility explanation and rescue route. Improve destructive USB confirmation contrast and control descriptions.
- Replace permissive marker-only ISO validation on real USB flashes and release sidecars with a bounded ISO9660/El Torito preflight requiring a hybrid partition record, Linux kernel, initramfs, squashfs and BIOS+UEFI boot catalog entries. Placeholder ISO images are now rejected, rather than flashed with false confidence. Boot remains UNVERIFIED without real VM/hardware boot tests.
- Retire the obsolete bootloader-only PowerShell ISO script. Strengthen the Debian live-build structural check, and remove `python3-tk` from the ISO package list. Tests use synthetic media only; **no physical USB boot or HDD repair has been validated in this revision**.
- Remaining qualification gates: Qt native Windows visual/behavior testing, full Tk feature parity review for niche offline/volatile refresh controls, verified Debian live ISO build, BIOS/UEFI boot tests, hardware USB flashing and controlled real HDD writes. Do not advertise complete parity or boot qualification prematurely.


## Unreleased — 2026-11-19 USB capacity-integrity spot test and visual reports (0.3.3b19)

- Introduced opt-in **temporary write/restore** capacity-authenticity spot checks for externally selected USB storage in engineering/guarded builds, and regular-image fixtures for safe automated tests. A 4 KiB preimage is durably journaled before each write; two matching restore reads are required; an unverified restore stops all further writes and preserves the recovery journal. **Spoofed-capacity controllers can still overwrite untested locations.**
- Added an original offline HTML evidence report: declared capacity, observed coverage, sampled-address heatmap, read/write latency distributions, per-position results and plain-language next steps. Sparse samples never masquerade as continuous verified capacity.
- Replaced visible manual HDD maintenance levels in the Qt workstation with an evidence-aware automatic consistency budget. Write eligibility and human consent remain independent.
- The prior Tk interface remains available until its deleted-file, filesystem and other specialized workflows are feature-parity tested in Qt; this release does not remove it.
- Added fault-injection tests for corrupt reads, interrupted restores, result classification, HTML escaping and refusal to overwrite existing reports. Physical-device validation is still pending.
- Windows fix: open capacity image fixtures with ``O_BINARY`` and use the shared positional ``pwrite`` helper so probe patterns are not text-mode mangled and mocked ``os.pwrite=None`` still falls back correctly.
- Windows journal durability: retry `os.replace` on transient WinError 5/32 when updating `meta.json` / region blobs during rapid capacity spot tests.


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
