# DriveRepair release status — post-b13 hardening (unreleased)

**Repository source baseline:** 0.3.3b13 plus the changes in the `CHANGELOG.md` Unreleased section. The version in `desktop/pyproject.toml` remains 0.3.3b13; no public version number or tag is declared by this patch.

**Release recommendation:** image-first public beta *candidate only*. Publish solely a `DriveRepair-0.3.3b13-public-beta.pyz` built with `python scripts/build_desktop.py --public-beta --no-wheel`, after review and manual platform smoke tests. The source checkout and normal wheel/zipapp retain raw-write engineering capabilities and must NOT be presented as the public beta binary. The package policy is a safety default for unmodified builds, **not a tamper-resistant sandbox or OS permission boundary**.

## Confirmed from this source-review environment

- Synthetic Python desktop test suite runs without touching real devices; actual result and skips are documented in the handoff report alongside this patch.
- Python compilation and a public zipapp smoke/negative command test can be run here.
- Regular-file image diagnostic, rescue and journal behaviors have synthetic tests, not independent full-scale hardware correctness certification.
- The GUI surface map reports actual observed readable fractions rather than interpreting sampled blocks as whole-drive health.
- Native Rust compiler/Cargo was **not available in this review environment**; Rust correctness and parity remain to be demonstrated in normal CI.

## Supported paths vs unproven paths

| Area | Source state | Remaining gate |
|---|---|---|
| Regular image scanning / rescue / resume and progress reporting | Implemented; synthetic coverage | Multi-OS tests, corrupt journal/large sparse images, destination-full faults |
| Windows external diagnostic scans | Implemented read-only | Native Windows 10/11 USB, 512e/4Kn, RAW/inaccessible partitions, stalled I/O and STOP |
| Linux external and offline internal disk rescue | Source paths present; read-only | Privileged sacrificial-hardware tests, all holder/mount and destination races |
| macOS read-only disk workflows | Source paths present | Real macOS inventory, privacy/permission and disk access tests |
| In-place refresh of patient disk | Engineering-only | Independent write-handle/device-binding review, full crash/USB/power fault matrix; **never in public image-first build** |
| Deleted-file and filesystem recovery | FAT32, Sleuth Kit, archive/file carving and clone-based work | Known-ground-truth test corpus, malformed/adversarial input audits |
| Rust regular-image core | Optional standalone implementation | Cargo fmt/clippy/build/test, Linux/Windows/macOS parity, fault and speed benchmarking |
| Boot recovery, firmware, sanitization | Experimental/unverified or not implemented | Separate designs and qualification before marketing |

**Recovery semantics:** successful sector read ≠ known-original bytes. Failed/untested areas stay UNKNOWN. An image file's apparent size ≠ recovered bytes. A rolling sector journal ≠ full patient backup. No benchmark supports 'better/faster' claims over commercial recovery products yet.

Historical `docs/PROJECT_STATUS.md`, `status.md`, and previous docs refer to earlier snapshots or operator reports. They are preserved for traceability; do not substitute them for this release status. In particular, `status.md` reports an operator-performed short SMR rewrite test, but that report alone is not independent crash/power-loss qualification.
