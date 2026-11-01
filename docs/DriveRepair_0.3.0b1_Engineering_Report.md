# DriveRepair 0.3.0b1 Engineering / release handoff

**Date:** 2026-11-01  **Source:** uploaded `DriveRepair-main(3).zip` snapshot (not verified against current Gitea HEAD)  **Verdict:** Engineering beta candidate; **do not advertise as a finished commercial or DoD-compliant recovery utility.**

## Implemented in this change

| Workstream | Code / workflow | Evidence | Limits |
|---|---|---|---|
| Targeted FAT32 undelete | `fat32_undelete.py`, `list-deleted-fat32`, repeated `--file-id` in `undelete-fat32` | Unit tests, image-to-extract end-to-end portable PYZ smoke | Contiguous unallocated clusters, partial 8.3 names, unverified contents; no overwritten-byte reconstruction |
| Multi-file GUI selection | `gui.py` new **Recover deleted files** tab | GUI source syntax and CLI integration tests | Real Tk interactions must be checked on Windows/macOS/Linux display |
| Optional filesystem-aware undelete | `tsk_recovery.py`, TSK `fls`/`icat` adapter, same GUI backend | Mocked tool tests | Installed TSK required; real-filesystem lab datasets still missing; may fail fragmented/overwritten files |
| Fast triage scan | `scanner.py` deterministic stratified probes plus bounded neighbor escalation | Synthetic probe/error tests + packaged triage smoke | NOT a full scan, does not prove unused areas healthy, latency affected by OS cache |
| Guided workflow | `gui.py` goal-first tab with links to workspaces | Static/syntax and desktop build | UX usability and accessibility tests still needed |
| Automatic multistage imaging | CLI `rescue-image --multi-pass` option invokes previously tested rescue + retry of missing regions | Packaged clean image smoke, rescue unit regression | First pass plus one bounded targeted retry, not ddrescue feature parity, no proof of failing-disk superiority |
| Rust native regular-image I/O | New standalone `rust/recovery-core` std-only crate with forward copy/reverse subdivide/journal | Rust unit tests added; CI build/test configured | **NOT compiled here, Cargo absent.** Raw devices expressly unsupported. `.rmap` incompatible with Python `.rescue.json`; Windows resume rejected |
| Scheduled monitoring | `monitor.py` + `monitor-external` | Synthetic history/status tests | Read-only SMART trend by default; opt-in samples; never autonomously repairs; SMART may be unavailable via USB |
| Forensic hash report | `forensics.py` + `evidence-image` | Unit tests + portable SHA-256 report smoke | Reports a hash of read bytes, not validated chain of custody or sector-for-sector acquisition |
| Installer/documentation | Updated source README, desktop guide, release gates, architecture, monitor/boot/benchmark guides, Gitea CI | Source archive, Python wheel/PYZ built | No signed `.exe`/`.app`, no validated bootable ISO; native platform hardware tests remain |

## Verified local tests

- Python source: `python -m unittest discover -s tests -q` — **126 total, 125 passed, 1 skipped** (Windows-specific test skipped on Linux).
- `python scripts/build_desktop.py` — built portable Python `.pyz` and installable pure-Python `.whl`; no Python package dependency downloads were required.
- Portable `.pyz` smoke: listed FAT32 candidates, extracted one selected known file, read-only triage-scanned its image, wrote redacted SHA-256 evidence manifest, rescued an image using `--multi-pass`, and byte-verified the result against its known source. **PASS**.
- `git apply --check` against a clean extract of the EXACT uploaded ZIP: **PASS**.
- Source archive excludes build directories, compiler outputs, caches, and `.egg-info` from the uploaded project.
- No personal physical drive was modified, erased, or repaired during this work.

## NOT TESTED / currently BLOCKED

- Rust `cargo build` or `cargo test`: compiler toolchain not present. CI will run on Gitea after push, but this is not already proven.
- Native Windows/macOS GUI/permissions/USB/volume-lock testing, and hardware imaging under disconnect / power failure.
- Actual TSK deletion/extraction on real NTFS/exFAT/ext filesystems (mocked tests only).
- Physical in-place media refresh: watchdog and journal require independent fault-injection with sacrificial hardware, not valuable disks.
- Properly verified native bootable rescue ISO for failed OS drives; existing BIOS/UEFI Rust boot sources retained but experimental.
- FDA/DoD/NIST or other certification; do not claim that seven writes makes the drive government approved.
- Firmware recovery/flashing, which must be vendor/device-specific, signed, separately authorized and validated.
- True automatic optimization/rejuvenation: this build schedules read-only warnings, not automatic patient rewrites.
- Any claim of faster, safer, more accurate, or 'better than all competitors' without paired controlled head-to-head recovery metrics and negative results.

## Safety principles applied

1. Select drives with model, capacity, bus, location, masked serial and a fingerprint. Never substitute guessed `/dev/sdX` or PhysicalDrive number for identity; hotplug changes these.
2. For deleted files, first list candidate metadata, then restore only selected IDs into **new** output folders, rechecking allocation; report speculative recovery explicitly.
3. Triage sampling is reproducible and finite. A quick clean sample is not a media health certification.
4. Default rescue and forensic workflows never write to the patient; separate destructive media refresh remains clearly gated and marked experimental.
5. RAM-backed journaling remains optionally volatile in existing Linux mode and is NOT a backup, even with UPS backing.
6. Secure sanitization must follow organization-approved media-specific standards. NIST SP 800-88 Revision 2 (September 2025) refers to IEEE 2883/NSA/applicable organizational standards; seven host write passes cannot reach all SSD/FTL or remapped media by guarantee.
7. Never auto-rewrite sectors based only on a benchmark slowdown. A deteriorating HDD should be imaged before intervention.

## Research and references

- GNU ddrescue 1.30 manual (2026), multi-phase algorithm: https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
- The Sleuth Kit file metadata and undelete tooling: https://wiki.sleuthkit.org/TSK-Tool-Overview/
- NIST SP 800-88 Revision 2 (2025): https://csrc.nist.gov/pubs/sp/800/88/r2/final
- Backblaze public Q2 2026 drive reliability data: https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data

## Cursor / Gitea handoff

1. Open the authoritative Gitea repository; ensure HEAD matches the uploaded source (or review/rebase patch instead of force-applying).
2. Create a feature branch and apply `DriveRepair_0.3.0b1_Upgrade.patch` with `git apply --check` and `git apply`.
3. Run desktop test suite on Windows/macOS/Linux. Install the Rust toolchain and run `cargo test --manifest-path rust/recovery-core/Cargo.toml`, `cargo build --manifest-path rust/recovery-core/Cargo.toml --release`. **Do not ignore failures.**
4. Perform image-only smoke tests from packaged artifacts, including corrupted state and reallocated FAT32 entries, and test the optional Sleuth Kit adapter with real filesystem image fixtures.
5. Independent security review of all raw-write paths, then sacrificial-disk hardware and USB/power-loss tests. Do not enable consumer raw-device refresh before gates pass.
6. Publish as **experimental source preview** only if licensing/secrets review and CI pass, with clear disclaimers. A first hardware-repair public beta requires the release gates in `docs/PUBLIC_BETA_GATES.md`.

**Release decision:** Source has materially improved but is not certified public-beta complete. The Rust core and physical/hardware claims remain unverified.
