# DriveRepair b28 — Source Hygiene and Runtime Audit

**Scope:** Source ZIP `DriveRepair-main(20261120-004204).zip`, supplied November 19, 2026. Read-only source analysis and synthetic fixture tests; no physical disks were accessed. This is an engineering audit, **not** a complete functionality or hardware qualification certificate.

## Audit results and changes

| Area | Evidence | Action / disposition |
|---|---|---|
| Python regression baseline | 557 passed, 11 skipped; 41 subtests; one collection warning | Preserve existing behaviour; extend tests |
| Dropped scan observations | `ProgressEmitter` cleared buffered read spans on phase change | **Fixed**: flush under SCANNING before publishing another phase; retain unsent spans on transient sink errors |
| Lost checkpoint retry opportunities | `ScanCheckpoint.save` set throttle timestamp before durable replace | **Fixed**: timestamp updates only after completed replacement/durability steps |
| Unnecessary source distribution size | Original archive 121.34 MiB compressed; 158.60 MiB uncompressed generated Rust `target/` files; 71.71 MiB historical nested release archives | New clean-source packager excludes only generated binaries/archives/caches, preserving Rust/Python/Qt/boot recipes/tests/catalogs/docs |
| Misclassified “dead” code risk | Console modules are called by CLI; Qt callbacks and recovery modes are accessed dynamically | **Retained** until usage proves removal safe. Do not infer dead code from a grep result |
| Pytest warning | A fixture named `TestReader` was mistakenly considered a test class | Renamed helper to `SyntheticReader` |

## Coverage evidence

The baseline synthetic run measured **58% overall Python statement coverage** in Linux/Python 3.13, which is **not** a measure of production readiness. Important gaps: native Qt module ~2% (PySide6 unavailable), Windows-native storage IOCTL ~46%, USB flashing ~57%, Windows ISO builder ~43%, exFAT parser ~14%, and CLI ~67%. A few modules have far higher fixture coverage. These unexecuted or skipped branches are **not automatically dead code**.

A randomized interval-union stress check validated 105,000 `CoverageCell` insertions against an independent byte-set reference. This is an algorithmic sanity check, not a hardware read benchmark. The modified progress path processed 100,000 synthetic events in approximately 0.07 seconds in this environment; timing is machine-specific.

## Release gates still unresolved

- Actual repair outcome on a sacrificial HDD: pre/post independent reads, source-data identity, journal rollback, controller remap/SMART changes (where available)
- USB disconnections, locked Windows kernel I/O, refusal of exclusive access, UASP/SAT bridge diversity
- Native Windows/PySide6 GUI interaction, navigation, keyboard, high-DPI and async progress
- Rust compilation and tests (Rust toolchain unavailable in this execution environment)
- Debian live ISO BIOS/UEFI hardware boot, USB writer verification, interruption recovery
- Incomplete filesystem extraction/repair coverage and file carving performance/accuracy

**Do not disable the write gates or claim 100% drive repair.** Stable recovery performance must be measured on real hardware with known-good data. Keep selected source, journal, destination and logs separate; use disposable drives for any physical-write tests.
