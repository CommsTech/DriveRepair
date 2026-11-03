# Public beta release gates — post-0.3.3b13 (unreleased)

**Current source status:** see [RELEASE_STATUS.md](RELEASE_STATUS.md). The historical gate details below remain requirements, not verified passes. The image-first public package now has a tested build-policy guard for raw physical writes, but the hardware, native GUI and signing gates remain open.

**Public package policy gate:** verify `python scripts/build_desktop.py --public-beta --no-wheel`, then run direct CLI deny-path tests against the generated `.pyz` (`care-image`, `refresh-image`, `care-external`, `refresh-external`, `refresh-system`, `optimize-volume --execute`). This does not qualify an engineering wheel or source checkout for public distribution.

**Decision: NOT READY FOR UNRESTRICTED PUBLIC BETA.** This package is suitable for controlled synthetic and nonvaluable image-based tests. The following work is NOT claimed complete:

| Gate | Requirement | Current status |
|---|---|---|
| A: Raw-drive safety | Independent audit of every raw write; correct mounted/held/OS/USB identification across Windows/Linux/macOS | NOT PROVEN |
| B: Journal crash safety | Force termination, host power loss and USB unplug during physical write on sacrificial drives; no silent success | NOT PROVEN |
| C: Rust core | Compile, clippy, test, benchmark and cross-OS compare to Python reference; prove map consistency | SOURCE IMPLEMENTED, BUILD NOT VERIFIED HERE |
| D: Cross-platform physical recovery | Windows/macOS volume locking, separate destination checks, 4Kn/USB bridge handling | NOT PROVEN |
| E: Deleted-file accuracy | Ground-truth datasets for FAT32 and Sleuth Kit backends; deleted, overwritten, fragmented cases | SYNTHETIC TESTS ONLY |
| F: Boot recovery | Boot actual ISO/USB on UEFI/legacy hardware; NVMe/USB/SATA access and safe destination selection | EXPERIMENTAL, NOT VERIFIED |
| G: Sanitization | Approved media-appropriate clear/purge/crypto-erase per organization policy, verified and audited | NOT IMPLEMENTED |
| H: Firmware remediation | Vendor-approved firmware tools, signed image provenance, supported hardware policy | NOT IMPLEMENTED |
| I: Packaging | Signed/native binaries and repeatable install/remove/permissions tests for Windows/macOS/Linux | PYZ/WHEEL ONLY; NOT PROVEN |
| J: Comparative benchmarks | Public datasets and real failing-disk experiments against established vendors | NOT PROVEN |
| K: Forensic claims | Independent chain-of-custody and write-blocker validation, provenance and hash evidence | NOT CERTIFIED |

## Why not seven-pass as 'DoD approved'?

Seven alternating overwrites are NOT a blanket Department of Defense certification. The current NIST SP 800-88 Revision 2 (September 2025) delegates specific sanitization technique details to applicable standards (e.g. IEEE 2883), NSA specifications or organizationally approved procedures. HDD host writes may not reach reallocated sectors. SSD FTL/overprovisioning makes host overwrites particularly unreliable; prefer supported, verified device-native sanitize/crypto-erase operations where appropriate. Sanitization cannot prove future drive serviceability; post-sanitize capacity, SMART and read/write tests are a SEPARATE assessment. Never advertise compliance without validated process and customer-specific authorizations.

## RAM journaling and automatic rejuvenation

- RAM journaling can reduce temporary disk I/O on Linux when backed by tmpfs, guarded by local power signals, and explicitly accepted as VOLATILE. A UPS doesn't protect against crashes, host reset or USB bridge failure. Disk-backed journal is the default.
- Scheduled **read-only** health alerts are implemented. Autonomous writes to a drive that starts slowing down are NOT safe by default; the same slowdown may be an early failure warning requiring immediate imaging and replacement. Any future automatic repair would require proven backups, independent evidence, workload-aware policy and strict user opt-in.
- Firmware repair is highly vendor/device-specific and can brick a disk or eliminate recoverable data; no universal flashing functionality will be shipped as beta.

## Beta publishable subset after gates

The public website can present **experimental image-only** features, with explicit limitations and an installation warning, after code review and CI pass. It must not market untested raw-media refresh, DoD sanitization, native boot recovery, complete cross-filesystem undelete or guaranteed data restoration. Avoid collecting customer images, file contents, serials, or identifiable logs for telemetry.

### Final-cycle additions

A read-only offline internal-disk rescue path to separately mounted local or
recognized network storage and an experimental Debian live ISO recipe were
added; neither proves BIOS/UEFI bootability or physical-media correctness.
The live ISO must be built, BIOS/UEFI boot-smoked, firmware/platform-tested and
independently reviewed before distributing it. The desktop CLI/GUI does not
magically turn a one-disk system into sufficient backup capacity. See
`ONE_DRIVE_RECOVERY.md`, `TRUSTED_PREVENTIVE_MAINTENANCE.md`,
`FINAL_RELEASE_SECURITY_REVIEW.md`.
