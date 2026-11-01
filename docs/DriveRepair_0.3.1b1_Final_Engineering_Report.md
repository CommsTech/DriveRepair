# DriveRepair 0.3.1b1 — Final engineering cycle, verification and handoff

**Date:** 2026-11-01  
**Input:** user-supplied `DriveRepair-main(4).zip`  
**Output:** `DriveRepair_0.3.1b1_Final_Candidate_Source.zip`  
**Verdict:** **ENGINEERING BETA CANDIDATE; NOT APPROVED FOR UNRESTRICTED PUBLIC BETA**.  
**Why:** Synthetic tests pass, but independent review, boot tests, real-hardware USB power-loss tests, Rust compilation in this sandbox, and native Windows/macOS physical-drive validations remain unproven. Do not market verified real-drive safety, universal repair or superiority.

## Direct answers

1. **UEFI and legacy BIOS bootability:** The original experimental Rust boot trees are present but do **not** establish a functioning integrated recovery boot image. A new `scripts/build_live_iso.sh` produces a Debian live-build recipe targeting BIOS GRUB-PC and UEFI GRUB-EFI, but no ISO was produced or boot-tested here. `scripts/check_live_iso.sh` is structural inspection only. Do not distribute a boot ISO yet. Secure Boot support is NOT_PROVEN.
2. **One internal drive recovery:** On a trusted Linux live USB, `list-all-linux` enumerates whole disks including unmounted internal disks. The new `plan-system-recovery` preflights identity, offline status and separate destination free space; `rescue-system` images to a healthy external device or recognized mounted NFS, NFS4, CIFS, SMB3 or SSHFS share. You cannot create a safe complete 12 TB image on the same sole failing 12 TB disk. Priority-file rescue is an alternative with a smaller separate destination.
3. **Documentation:** Updated the active readme, desktop readme, architecture, project status, changelog, security, beta gates, boot/recovery and OpenClaw handoff. Historical versioned notes are snapshots, not updated in place. The docs state what remains experimental.
4. **Can every feature be certified operational?** No. Python unit and packaged image tests pass, but no physical hardware was exercised and there were no Rust toolchain, QEMU or live-build programs available in this sandbox.

## Changes delivered

- Added `linux_all_devices` and explicit `select_linux_any_disk`: internal drives are intentionally excluded from ordinary `list` and normal desktop browsing.
- Added Linux CLI `list-all-linux`, `plan-system-recovery`, `rescue-system` with 12-character identity check, `--ack-risk`, `--ack-offline-system`, source read-only handling and repeat identity checks.
- Added mounted NFS/CIFS/SSHFS destination acceptance, while rejecting unknown pseudo filesystems and physical ancestry overlap; no silent acceptance of a local destination on the patient disk.
- Added one-drive GUI selection panel and goal-based offline recovery walkthrough.
- Added proactive SMART alert on FIRST observation of nonzero media error/pending sector counters. A previously unobserved bad drive should not receive a false clean baseline.
- GUI health indication starts UNKNOWN, not an unsupported green OK.
- Added project Debian iso-hybrid BIOS/UEFI recipe with no automatic USB writes; ISO must be built and independently validated.
- Added `docs/ONE_DRIVE_RECOVERY.md`, `docs/TRUSTED_PREVENTIVE_MAINTENANCE.md`, `docs/FINAL_RELEASE_SECURITY_REVIEW.md`, and `docs/OPENCLAW_ENTREPRENEUR_HANDOFF.md`.
- Added Gitea CI job for Linux offline recovery testing and script structural validation, preserving existing platform-specific jobs.
- Updated Python packaging to `0.3.1b1`.

## Validated test evidence

| Test class | Result | Significance and limits |
|---|---|---|
| Baseline Python unit suite from input | **141 tests, OK (1 skipped)** | No real drive touched |
| Expanded Python unit suite | **148 total: 147 passed, 1 Windows-only skip** | Device inventory, remote mounts, selected fingerprint, first-alert SMART, synthetic whole-drive rescue |
| Python `compileall` | **PASS** | Syntax/import packaging only |
| `scripts/build_desktop.py` | **PASS** | Built pyz and wheel; tests run during packaging |
| Packaged PYZ smoke | **PASS** | Regular-image rescue to output, mapfile, byte-for-byte verification, sampled triage, offline command help |
| `bash -n` for ISO build and inspection scripts | **PASS** | Bash syntax, **not** an ISO build or boot |
| Git patch apply against exact supplied baseline | **PASS** | `git apply --check` and clean application |
| Gitea CI YAML parse | **PASS** | YAML parses, **not** an actual Gitea CI run |
| Native Rust compile/clippy/cargo tests | **NOT RUN** | Cargo and rustc not installed in this sandbox |
| ISO generation / BIOS + UEFI boots | **NOT RUN** | Debian live-build, QEMU and xorriso not available |
| Windows and macOS native hardware testing | **NOT RUN** | No appropriate test environments |
| Real raw-drive, USB-dock failure, power-loss, journal validation | **NOT RUN** | No physical writes or patient disk touched |
| Independent professional security / privacy audit | **NOT RUN** | Local static review is partial, not a penetration test |

### Existing functionality retained

Python desktop GUI / CLI, external-device scans, deterministic quick triage, image rescue, partial map/resume, selective FAT32 deleted-file extraction, optional Sleuth Kit file catalog/recovery, file carving, ZIP salvage, image checksum evidence, cloned-ext repair, manual experimental refresh and RAM-backed journal, SMART trending, experimental Rust image-only core. **Presence does not imply full platform/hardware proof**. Current desktop orchestration and major I/O are still Python, not universally migrated to Rust.

## Threat review / outstanding problems

- **P0 – Raw-device refresh is destructive:** A rolling journal is not a full backup. Even read-verified in-place rewrites can destroy the last useful data if the disk, controller, bridge, host or journal fails. The existing high-friction acknowledgments and identity checks are defenses, **not** proof of safety. Require independent fault-injection testing before exposing this to general beta users.
- **P0 – Boot image unverified:** A live-build recipe is not proof of BIOS+UEFI+Secure Boot support. Complete VM and sacrificial host tests, signature/provenance review, then release checksums before offering this feature.
- **P0 – No one-disk full backup without other capacity:** A journal or UPS-backed RAM storage cannot substitute for 12 TB of verified destination capacity or physically diverse copies.
- **P1 – Cross-platform uncertainty:** Windows/macOS low-level raw access and filesystem locking have not been exercised on real devices. Do not claim universal hardware compatibility.
- **P1 – Integrity:** A successful read is not equivalent to ground-truth data. Testing needs known hashes, source identity, file-system invariants and a failure map that never reports missing sectors as recovered.
- **P1 – Sensitive data exposure:** Forensics/undelete can surface private content, file paths and serials. Default reporting should redact, local storage permissions should be verified, and users should explicitly choose export/case sharing.
- **P1 – Third-party tools:** `fls`, `icat`, `e2fsck`, `smartctl`, `findmnt`, network mounts and live ISO packages need pinned versions, parser fuzzing, supply-chain analysis and failure-path tests. Current Python subprocesses generally use argument arrays rather than shell interpolation, but this is not a complete code/security audit.
- **P1 – Hardware health:** Remapped sectors may restore readability without repairing scratched platters, worn heads or NAND endurance. A passing refresh does not justify a “like new” claim.
- **P1 – Sanitization:** A seven-pass overwrite does not make a product DoD-approved. NIST SP 800-88 Rev. 2 (Sep 2025) calls for media-appropriate techniques and organizational controls; SSDs and hidden/reserved areas need different handling. Erasure certification and subsequent drive health verification must be assessed separately.
- **P2 – Usability and performance:** Real workloads should compare verified recovered bytes and incorrect “success” reports first, then time-to-first-priority-file, throughput, I/O amplification, thermal stress and energy. Optimizing raw throughput alone can damage recoverable patient drives.

## Why autonomous repair is not enabled

Drive slowness can indicate correctable weak magnetic/flash data, but also worn heads, firmware trouble, heavy USB retries, power instability, filesystem fragmentation, operating-system load or a dying disk. Automatic writes to an at-risk source can cause irreversible damage and cannot create a full backup. A safer graduated automation model:

1. **Always-on, read-only SMART trending:** establish first-baseline alerts, log metrics and warn, including drive identity and current provenance. Keep state off patient.
2. **Opt-in bounded sample reads:** measure weak regions but state that quick scan cannot prove the rest of the disk sound.
3. **Automatic copy-to-separate verified destination when owner-authorized and a stable destination exists:** prioritize data preservation and notification.
4. **Optional in-place refresh only when known-good redundant copy/verified recovery exists and hardware-specific policies and independently tested journal guarantees are satisfied:** explicit owner authorization, never unattended on unknown valuable drives.
5. **Verify post-operation media/readability and retain before/after evidence:** fail closed; recommend replacement for repeatedly failing media.

A UPS reduces one class of power failure but does not make volatile RAM crash-proof or guarantee an externally powered USB dock stays on.

## Honest positioning and next market steps

- Beta promise: privacy-first guided recovery; local-first evidence, clear health uncertainty, upfront risk warnings, image-first salvage, selective file recovery.
- Publish objective competitor measurements for GNU ddrescue, OpenSuperClone, The Sleuth Kit, filesystem-specific recovery tools and paid utilities, with paired ground-truth test images and equal stop/retry budgets. **Do not claim 'faster, safer, better' until measured.** GNU ddrescue 1.30 itself has five mature passes: copying, trimming, sweeping, scraping, retrying.
- Pricing: consider free image-only experimental beta and monetization through independently validated convenience, managed fleet reporting, signed enterprise builds, professional support and validated forensic workflows. Obtain user/customer research rather than guessing willingness to pay.
- OpenClaw entrepreneur delegation instructions are included at `docs/OPENCLAW_ENTREPRENEUR_HANDOFF.md`. Marketing, publication, destructive device tests and pricing changes are **not** authorized by this code handoff.

## Artifact checksums (SHA-256)

```text
524b7f64576fc91d7b0c1ee84d6e34ddacc75c1f5525179c06f4fa1a3dc86e53  DriveRepair_0.3.1b1_Final_Candidate_Source.zip
15b7172ec8e9d2d38936889d9d1a970cb42ab8b864a7c93a865905107eb3f414  DriveRepair_0.3.1b1_Final_Cycle.patch
49867ce57d1d3e6593caa01ac85df8c36e7b9736693eb47cc60b2a1bccb8cbe7  DriveRepair-0.3.1b1.pyz
603da52dbb08b78af4925d8425909828f0443b66097b30ef5ce1b8449a9a89d2  driverepair_desktop-0.3.1b1-py3-none-any.whl
```

## References

- GNU ddrescue v1.30 manual (2026): https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
- NIST SP 800-88 Revision 2 final (September 2025): https://csrc.nist.gov/pubs/sp/800/88/r2/final
- Backblaze SMART factors: https://www.backblaze.com/blog/what-smart-stats-indicate-hard-drive-failures/
- Debian live-build: https://live-team.pages.debian.net/live-manual/html/live-manual.en.html
