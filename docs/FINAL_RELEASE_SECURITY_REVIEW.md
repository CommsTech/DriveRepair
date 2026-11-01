# DriveRepair final engineering cycle — security, privacy, safety, release status

**Review date:** 2026-11-01. **Disposition: PUBLIC BETA NOT APPROVED.**
Code-review and synthetic test evidence are not equivalent to physical safety
or boot qualification. This document is the active release-gate summary;
historical documents under docs/releases and docs/release-readiness describe
older snapshots.

## Verified in this sandbox

- Python desktop unit suite and additional fake-disk integration tests run.
- Linux internal whole-disk inventory is separated from normal external-only
  inventory; recovery requires explicit offline acknowledgment and identity
  fingerprint. `lsblk` mounting and kernel-holder checks are reused.
- Destination verification now recognizes real, explicitly mounted network
  filesystems (NFS/NFS4/CIFS/SMB3/SSHFS) while excluding root overlays,
  tmpfs, unrecognized FUSE, and unknown ancestry.
- A system-image preflight reports destination free space before acquisition.
  Remote quotas can still surprise it; short writes and ENOSPC stop a job.
- First nonzero media-failure SMART baseline raises an actionable alert.
- Linux scheduled-monitor history is checked for storage separation before
  writing, to avoid a patient-drive history file.
- Experimental Debian hybrid ISO **build recipe** exists, but the ISO is not
  built here: neither live-build, xorriso, nor QEMU were present.
- GUI presents an offline OS-disk recovery guide and no longer starts with an
  unsupported default "media OK" health assertion.

## Important open risks / RELEASE BLOCKERS

| Severity | Risk | Required evidence |
|---|---|---|
| P0 | No boot-tested BIOS/UEFI image, Secure Boot unverified | ISO build + BIOS/UEFI VM logs + physical SATA/NVMe/USB boots |
| P0 | Raw media refresh is destructive and unvalidated on actual failing drives | Independent safety audit, sacrificial hot-unplug/OS crash/power fault tests, verify original data and journal |
| P0 | No complete backup on sole failing disk | Require separate storage, NAS, or prioritized-file rescue; never imply journal equals backup |
| P0 | Rust core has no native build proof here | Cargo, clippy, cross-OS tests, crash/map corruption tests and parity comparison |
| P1 | Windows/macOS hardware recovery, destination isolation, native install | Hardware QA including disk locking, filesystem and USB quirks |
| P1 | USB bridge duplicates/masks serials and may lose power | Disconnection/swap fault injection and stable device identity tests |
| P1 | Scan success does not establish contents correct | Known-hash reference datasets and filesystem-aware parity results |
| P1 | Automatic refresh not trustworthy on at-risk media | Backup checks, hardware-class-specific policies, controlled experiments |
| P1 | File-system undelete cannot restore overwritten data | Fragmented NTFS/exFAT/ext/Apple recovery accuracy evidence |
| P1 | No independent privacy/security code audit | Static/dependency scanning, fuzz parsers, extraction path limits, signed artifacts and disclosure process |
| P1 | No sanitization/forensic certification | Organization-approved technique and proof per NIST SP 800-88r2 / relevant standards; write-blocker evidence |
| P2 | UI/installer discoverability | Native signed bundles, accessible GUI testing, platform-specific beginner instructions |
| P2 | Competitor speed and correctness unverified | Controlled head-to-head benchmark protocol |

## Privacy and supply chain observations

- Built-in source operations default read-only; repairs to a filesystem image
  operate on a NEW clone. Raw-media refresh is isolated behind explicit gates.
- User disk images and SMART reports are not deliberately uploaded to a cloud
  service by application code. Standard OS utilities and optional external
  binaries need separate trust and version review.
- Evidence JSON redacts source path and serial by default; the original data
  may still appear in user-selected output files and some legacy logs.
- CLI subprocess execution uses fixed argument arrays; inspect all new
  contributions for shell interpolation, symlink/hardlink races and path escape.
- Boot-media build depends on Debian APT, its signing keys and reproducible
  published source. It is NOT the same as a signed firmware boot chain.
- Local hardware write controls are risk gates, not mathematical proof of
  non-destructiveness.

## Beta scope recommendation

Use a limited **image-only experimental beta** after native CI passes and
independent parser/security review. Keep physical refresh, native ISO download,
firmware operations, sanitization and automated source rewrites out of the
public GUI default until separately qualified. No vendor-superiority,
"data restored", "drive like new" or "DoD approved" claims without test evidence.
