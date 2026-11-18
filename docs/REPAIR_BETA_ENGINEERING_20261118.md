# DriveRepair guarded HDD repair beta — November 18, 2026

**Scope:** This is a working *experimental* guided in-place HDD maintenance path. It is **NOT** a qualified guarantee of disk or file recovery, restored reliability, or vendor-certified repair. Do not use on irreplaceable data without prior rescue. The default public image-first build remains available.

## Three truthful results

| Operation | What it changes | What it proves |
|---|---|---|
| Rescue physical drive to a NEW image | Never writes patient media | Bytes successfully read were saved to the target; gaps remain tagged in the journal |
| Journaled targeted physical HDD rewrite | Rewrites only repeatedly readable, bounded weak/error areas **with the original bytes** | Readback matched the original double-read digest at the time of the check; does not repair permanently unreadable sectors or exhausted hardware |
| Filesystem repair on a COPY of an image | Changes the cloned filesystem metadata | Selected filesystem structures became internally consistent according to the checker; not original-file checksum correctness |

**Neural reconstruction:** No trained, validated model or model weights exist in this repository for reconstructing missing sector data. Recovery ordering and media-specific thresholds are deterministic, evidence-based heuristics. It is incorrect to market them as an independently verified "neural recovery algorithm." Unsupported or unreadable sectors remain missing; never synthesize data and call it recovered.

## Implemented in this revision

- `--repair-beta` packaging channel, separate from `--public-beta` (image-first). The guarded build permits `care-external` but blocks broad full-surface refresh and image-in-place refresh commands. The Python engineering source remains a separate, explicitly unqualified distribution.
- Guarded mode requires *actual SMART evidence* establishing an HDD rather than trusting a USB bridge, model-name guess, or Windows coarse HealthStatus. Critical SMART/transport/thermal findings block writes. Media warnings need explicit additional consent.
- Drive-specific advisory routing: verified HDD/SMR/CMR → consider targeted rewrite after rescue; SSD/NVMe → controller health diagnostics and back up or replace; unknown → identify first. Raw reallocation, sanitize, TRIM, firmware update, and SSD full-surface write operations are not silently substituted for repair.
- Guarded operations require a **separate disk-backed rolling journal**, 16-region batch cap, no recording override, no neighboring rewrites, and Windows exclusive volume locking. The existing CLI preflight rechecks 12-character fingerprint, serial, patient idle state, journal separation and all acknowledgements.
- The Qt repair wizard requires active decisions acknowledging potential loss and SMART warnings. The image-first build still disables source writes. A separate recommendation is made when no hardware repair candidates are found.
- Each committed region now persists its prewrite SHA-256 digest alongside existing durable journal metadata. After the writer closes, an independent READ-ONLY open performs two matching reads and compares bytes against that digest. Mismatches/unavailable checks downgrade a successful completion to an error (where the records are present). Legacy journals remain marked *postverify unavailable*.
- Captures SMART counter differences after maintenance and downgrades the status when new reallocation, uncorrectable, CRC or NVMe media errors are observed; no status claims restored drive lifespan.
- Python tests cover release policy, HDD-vs-flash choice, SMART failures, transport and temperature failures, exact readback, corrupted metadata and unstable reads. A sacrificial *regular-file* journaled rewrite/readback smoke was run. None of this substitutes for USB/real-drive validation.

## Build and run

Requires Python 3.10+ and optionally PySide6 (`pip install PySide6`) for the redesigned Qt workbench. **Only do physical-repair testing on sacrificial HDDs with a separate healthy disk and stable power.** Install smartmontools (`smartctl`) for SMART evidence.

```bash
python scripts/build_desktop.py --repair-beta --no-wheel
python dist/DriveRepair-0.3.3b13-repair-beta.pyz gui
```

If PySide6 is not installed, `gui` falls back to legacy Tk; use `qt-gui` to require the redesigned Qt workstation. For a *read-only* preflight before trying any write:

```bash
python dist/DriveRepair-0.3.3b13-repair-beta.pyz list --json
python dist/DriveRepair-0.3.3b13-repair-beta.pyz health --device "<list device ID>" --json
```

The guided Repair workstation walks through target confirmation, explicit risks, and a separate-disk journal location. The engine performs a sampled or full *read-only* scan first, selects repeatably readable weak regions, and attempts only the planned transactions. If no such candidates exist, **zero write operations are performed**. This is correct behavior, not an algorithm failure.

## Why this will not "fix every bad sector"

Modern HDDs perform their own internal error correction, retries and remapping. An unreadable LBA does not provide the original data to rewrite. Forcing zeros over it can destroy forensic value. Firmware-managed reallocation may make a logical address accessible, but the original lost bytes are not recreated. SSD/NVMe controllers also manage flash wear and remapping; unnecessary whole-surface rewrites consume endurance and can worsen a failing drive.

The app does **not** attempt destructive vendor-specific command pass-through, security erase, sanitize, firmware updates, arbitrary sector reinitialization, or non-supported head tuning. These need device-specific specifications, independent protocol validation and informed, destructive consent.

## Research references (primary)

1. [GNU ddrescue manual](https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html) — multi-pass forward/reverse recovery, mapfile, trimming/scraping/retry philosophy.
2. [Seagate: bad sectors and reallocation](https://www.seagate.com/support/kb/what-do-i-do-if-my-drive-reports-bad-sectors-196351en/) — physical-sector remapping and data-loss risks.
3. [Microsoft: Working with NVMe Drives](https://learn.microsoft.com/en-us/windows/win32/fileio/working-with-nvme-devices) — protocol-specific health log retrieval via storage queries.
4. [smartmontools smartctl documentation](https://man.archlinux.org/man/smartctl.8.en) — ATA, SCSI/SAS and NVMe identity, self-test and error/health reporting.
5. [Microsoft chkdsk](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk) — filesystem metadata repair and differing `/scan`, `/spotfix`, `/r` scopes.
6. [e2fsck manual](https://man7.org/linux/man-pages/man8/e2fsck.8.html) — repair requirements for offline, unmounted ext filesystems.
7. [Microsoft SSD critical warnings](https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/what-to-do-about-a-critical-warning-for-a-storage-device) — NVMe reliability, read-only status, spare capacity, and endurance context.

## Not yet qualified: mandatory agent handoff

- [ ] **Windows 10/11:** PhysicalDrive selection and exact model/serial/fingerprint, USB dock, RAW/unmountable partitions, BitLocker, Administrator permissions, 512/512e/4Kn, exclusive lock and dismount (including blocked busy volumes). No C: or live system disk writes.
- [ ] **Linux live/offline:** Disk enumeration, no mounted children/holders, journal on a distinct physical drive, short reads and 4Kn alignment; physical adapter tested independently.
- [ ] **Power faults:** crash and unplug at `SAVED`, `WRITING`, `VERIFIED`, and `COMMITTED` phases; verify journal retention and exact restored bytes, then safe resumption under unchanged identity.
- [ ] **HDD real hardware:** Sacrificial CMR, confirmed SMR, unknown-recording rotational and USB bridge; A/B compare raw bytes, SMART before/after, bad-sector remapping where supported, block repeated degradation.
- [ ] **SSDs/NVMe:** Prove guided physical-write path remains blocked; check metadata and SMART counters, not inferred HDD heuristics.
- [ ] **Qt UX:** Run `qt-gui` with PySide6 on Windows; test navigation, focus/keyboard, scaling 100–200%, no accidental Start, distinct repair vs rescue states, safety dialogs and STOP between transactions.
- [ ] **Actual recovery:** Compare ground-truth corpus against GNU ddrescue and competent commercial tooling: verified recovered bytes, unrecovered extent map accuracy, source read amplification, percent file checksum matches, long-tail latency, USB disconnect recovery, peak RAM, CPU, sustained throughput.
- [ ] **Rust migration:** Compile/test the existing Rust regular-file rescue on Windows/Linux/macOS; then implement Rust raw I/O adapters and a durable writer only with independent code review and device access tests. **Do not swap Python raw handles for image-file Rust handles** or claim the current physical writer is Rust.
- [ ] **Release:** installer signing, reproducible build, security review, actual field evidence, and explicit warranty/limitations before broader marketing.

### Environment validation

- Python compilation: pass.
- Unit tests: **350 passed, 11 skipped, 19 subtests passed** (after health comparison additions; run again before publishing).
- Regular-image synthetic targeted rewrite: **2,048 bytes written, 2,048 independently re-read and SHA-256 matched; image content remained byte-identical.** This was an in-process image fixture, *not* an HDD remediation demonstration.
- Cargo/Rust compilation: **not available in this environment**; existing Rust source was not changed. Physical writer remains Python.
- Native Windows GUI and physical-device tests: **not performed**.
