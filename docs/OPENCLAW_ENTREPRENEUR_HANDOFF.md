# DriveRepair → OpenClaw Entrepreneur agent handoff

**Snapshot:** 0.3.1b1, 2026-11-01. **Release:** engineering beta candidate, NOT cleared for unrestricted public beta. **Authoritative source:** private Gitea repo until owner authorizes publication.

## Goal and honest positioning

A privacy-first desktop and eventually bootable disk diagnostic, image rescue,
selective deleted-file recovery, clone repair, and separately approved media
maintenance toolkit. Works offline by default, outputs transparent evidence,
and helps nonexperts choose the correct disk. **Do not market as able to repair
physical wear, universally recover overwritten data, certify DoD sanitization,
or beat every competitor without benchmarks.**

## Current demonstrated subset

- Python desktop interface with guided recovery, raw-disk external scanning,
  FAT32/TSK selective deleted-file operations and image workflows.
- Linux live environment offline-system disk inventory / preflight and read-only
  raw image recovery to a checked separate local/network destination.
- Read-only SMART monitoring with initial error baseline alerts.
- Optional, separate Rust regular-image rescue library (compile in CI; **not
  built natively in this sandbox**); Python GUI/CLI remains main interface.
- ISO-hybrid **build recipe** (Debian, GRUB BIOS+UEFI) with no verified boot
  artifact. Do not distribute a boot ISO until validated.

## Required stage-gated tasks before public announcements

1. Run all Gitea CI on Ubuntu, Windows, macOS, test Rust core Clippy/Cargo,
   obtain signed build artifacts and hashes. Reject unknown build results.
2. Build experimental live ISO in an isolated, known-good VM. Test BIOS and
   UEFI VM boots, then hardware SATA/NVMe/USB/network, mounting and raw source
   read-only controls. Record screenshots/logs and exact artifact SHA-256.
3. Get a second independent engineer to review filesystem parsers, symlink/
   path handling, binary extraction, raw write guard logic, USB identity and
   crash journal. Track each finding to an executable acceptance test.
4. Test sacrificial USB docks and drives, 512e/4Kn, SCSI SAT bridges, SATA/NVMe,
   mount swaps, network/storage quotas, interrupted copy/resume, live power
   loss, and source/destination device swaps.
5. Benchmark good drives and reproducibly fault-injected devices against
   GNU ddrescue / OpenSuperClone and file recovery tools. Measure verified
   recovered bytes, false successes, source writes, time, retry amplification,
   RAM usage, USB resets and user task-completion rates. Publish ALL results.
6. Keep autonomous media refresh and destructive firmware/sanitize functions
   disabled for valuable drives pending review and owner authorization.
7. Develop beginner docs, screenshots, permission guidance, portable installers
   and troubleshooters per OS. Make existing product limits visible in-app.
8. Conduct user interviews and pricing research **without inventing uptake or
   comparative superiority**. Consider free experimental beta and later paid
   convenience/support features only after trust and hardware evidence exist.

## Handoff requirements

Output a release readiness table with `VERIFIED`, `FAILED`, or `NOT_PROVEN`,
objective evidence (commit, test file/command, SHA, OS), fix owner, regression
case, and remaining risk. Do not change production disks, deploy public code,
publish store listings, modify payment settings or assert approval without the
owner's explicit authorization. Respect independent verification and the user's
native-first / minimal custom machinery preferences.

Mandatory docs: `docs/ONE_DRIVE_RECOVERY.md`,
`docs/TRUSTED_PREVENTIVE_MAINTENANCE.md`,
`docs/FINAL_RELEASE_SECURITY_REVIEW.md`, `docs/PUBLIC_BETA_GATES.md`,
`docs/BENCHMARK_PROTOCOL.md`, `SECURITY.md` and `docs/ARCHITECTURE_CURRENT.md`.
