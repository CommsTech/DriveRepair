# Changelog

## Unreleased — desktop external-drive scanner

- Added read-only **Windows, macOS, Linux** host scanning that does not require restarting the machine.
- Uses the host operating system to discover external whole disks rather than relying on incomplete experimental low-level firmware drivers.
- Adds bounded, streaming sample/full scans with read error classification, device re-identification and JSON result output.
- Added synthetic-image tests and mocked OS discovery fixtures; real hardware testing still pending.
- Disabled the host Rust demo's misleading repair menus; it now points users to the non-destructive desktop scanner.
- Removed legacy proprietary-binary analysis materials and obsolete progress claims from the current project tree.

## v0.0.1 — initial experimental scaffold

- Added Rust device abstraction, boot prototypes and command-line menu experiments.
- Hardware drivers, repair correctness, boot workflow and full-size scan performance were not independently verified.
