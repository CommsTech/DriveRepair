# DriveRepair — workstation and adaptive recovery handoff

Date: 2026-11-18
Status: **Source changes / engineering candidate only. No real-device repair certification.**

## Changes in this increment

| Area | Before | Now |
|---|---|---|
| Qt guided rescue | The Recover button silently selected an existing source image and requested another image | The default rescue goal reads a selected external disk **without source writes**, saves to a **new** image, and requires explicit risk confirmation. Image-to-image remains available as a separate choice |
| Qt workflow and UI | Dense status panels; no chosen-goal highlight; no journal map for rescue | Three labeled stages, selection highlight, keyboard focus styling, scrollable window, rescued/missing metrics, retry-pass progress, approximate journal map, saved-data rate |
| Failed-range recovery | First pass skipped failed chunks; retry split failed chunks once down to sectors with no additional sector-level retries or agreement test | First pass still skips errors quickly; retry splits, permits 0–2 extra attempts **only per logical sector**, and requires a fresh identical read before writing a newly recovered segment to the **destination** image |
| Engineering rewrite plan | When more safe candidates than configured budget, chose the earliest offsets | Bounded batch favors *repeatable-after-error* candidates and high-latency slow regions, then re-sorts by offset for deterministic journal transactions |
| Policy | Public beta prohibited patient in-place writes | **Unchanged**; CLI risk acknowledgements, source identity, mounted-volume and rolling-journal gates are not bypassed |

## What “repaired” can and cannot mean

- **Rescue:** actual readable source bytes can be copied into a new disk image. Previously unreadable ranges that become readable during a bounded retry can be recovered. The persistent `.rescue.json` map identifies missing data; sparse holes are **not** recovered bytes. The original disk's bad surface is not changed.
- **Targeted rewrite:** in a separately qualified engineering build only, already readable, consistently reread weak regions may be durably journaled, rewritten, and read back. A successful rewrite may cause device firmware to remap a marginal sector on some devices; it cannot prove permanent health, fix a controller, restore an SSD NAND cell, or infer unknown bytes.
- **Neural repair:** this repository has **no trained/validated neural model** that can reconstruct missing disk sectors. These changes improve the **real adaptive read/retry algorithm**, not a neural model. Two matching reads demonstrate *repeatability* only; without independent checksums/parity/replicas they do not prove originally correct data.
- **Never:** write manufactured bytes to patient media, auto-retry in-place writes after disconnect, relax identity/volume lock checks, or present every copied byte as integrity verified.

## Validation performed

From `desktop`:

```bash
PYTHONPATH=. python -m unittest -q tests.test_recovery_optimization
PYTHONPATH=. python -m unittest discover -s tests -q
python -m compileall -q driverepair_desktop
```

Synthetic/fault-injection coverage includes: recover transiently failing 512-byte logical sectors to an exact destination image; reject inconsistent readback without copying it; bound failed sector attempts; separate forward/retry progress; choose the highest-priority limited rewrite candidates. The complete Python suite reports **325 tests passing, 4 skipped** in this Linux sandbox at time of patch preparation.

A public-beta zipapp was then built with `python scripts/build_desktop.py --public-beta --no-wheel`.
Packaged CLI smoke test: image-to-image rescue returned status `completed`, output
bytes matched source bytes exactly, `rescue-status` returned `clean_rescue_complete=true`,
and attempting `care-image` was refused with a nonzero return code **before a repair
journal was created**. This is a simulated regular-file test, not live-drive validation.

## Remaining release gates — send to a hardware-enabled test agent

- [ ] **Windows 10/11 native PySide6 GUI:** verify all three goal buttons, keyboard/tab navigation, scroll behavior at 800×620 and 1920×1080, image versus physical source, file picker overwrite refusal, status colors and missing-sector legends. Qt is not installed in the sandbox; no GUI clickthrough was performed here.
- [ ] **Linux Qt/macOS Qt:** verify optional GUI installation, platform-specific display and accessibility, and source identity after reconnect.
- [ ] **Dedicated sacrificial external HDD over direct SATA and USB bridge:** recover a controlled drive to a separate healthy destination, verify source is opened read-only, compare the rescued image to a pre-recorded checksum, inspect journal after each phase. Never use unique/valuable data.
- [ ] **Injected reproducible read faults with an external programmable block device:** compare recovered bytes, error budgets, retry time, SMART/transport state before and after; ensure USB disconnect is treated as fatal, not a bad sector or partially successful repair.
- [ ] **Long-run resource/profile testing:** 1/4/8/16 TB test images (sparse where practical), high fragmentation of missing ranges, repeated STOP/resume and low destination free space; track peak memory, journal write cost, throughput and GUI event latency.
- [ ] **Physical in-place maintenance (private engineering build only):** isolated bench with sacrificial known-media CMR/SMR HDD, SSD and USB bridge matrix; operator-reviewed consent, exclusive volume lock, separate durable journal, actual power-loss/crash tests, pre/post full-image checksums and SMART counters. Stop at the first unverifiable or uncertain result; do not qualify a public release based on synthetic tests.
- [ ] **Release distribution:** build `--public-beta`, verify physical and image in-place write commands are denied **from the packaged artifact**; review third-party PySide6 licensing, documentation, platform signing and installer.
- [ ] **Rust/boot QA:** Rust toolchain not present during this review; no Cargo, BIOS or UEFI compilation/runtime result is asserted.

## Integration instructions

1. Apply `DriveRepair_2026-11-18_UI_Rescue_Optimization.patch` from repository root (`git apply --check`, then `git apply`). Or use the accompanying clean source archive.
2. Create an isolated Python environment, install `-e 'desktop[qt]'` (or install PySide6 separately), run `python -m driverepair_desktop qt-gui` from `desktop`.
3. Run the full unit suite above and the manual gates before shipping.
4. Preserve old recovery journals. Do not delete or overwrite `.rescue.json` or `*.rescue.lock` when resuming.
