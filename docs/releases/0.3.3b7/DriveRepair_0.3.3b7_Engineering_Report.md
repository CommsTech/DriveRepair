# DriveRepair 0.3.3b7 — Adaptive Scanning & Guided UX Engineering Report

**Date:** 2026-11-02  
**Input:** User-supplied `DriveRepair-main(9).zip`  
**Output:** Source ZIP, portable `.pyz`, installable `.whl`, and Git patch.  
**Disposition:** **EXPERIMENTAL — synthetic testing passed; public beta and real-disk write qualification remain open.**

## Objective

Avoid wasting hours rescanning the same good sectors after a local I/O error. Make a job selection deliberate and approachable for nonexperts. Reduce missing-prerequisite confusion without silently installing privileged software. Keep previous anomaly information useful without storing disk content or weakening write authorization.

## Changes implemented

1. **Adaptive full scan.** Introduced `desktop/driverepair_desktop/adaptive_scan.py`: start with aligned 1–4 MiB reads, grow to 8 MiB under sustained success, reduce/defer on I/O errors, and return with bounded smaller requests. Repeated unreadable regions can be skipped provisionally as **untested** so the sequential pass can continue. Deferred investigation uses explicit budgets; no disk writes during scanning. Log actual `read_sizes_bytes` and `read_size_adjustments`.
2. **Windows I/O error classification.** `winerror=1117` is treated as an I/O device error, even if Python also reports `errno=22`. It is **not proven** to be magnetic media failure; cable, bridge, power, transport, controller and media remain possible causes. Fatal access denial, identity mismatch and device loss still stop the operation.
3. **Bounded repair planning.** Where more independently readable weak regions are found than the repair budget permits, the planner reports an eligible subset and explicitly reports remaining candidates rather than treating the whole drive as repaired or rejecting all progress. In-place refresh still needs separate approval and verified readable original bytes.
4. **Optional anomaly history.** New `scan_history.py` persists only weak/bad/skipped offsets and classifications under a device-derived key in local application state. `--remember-anomalies` and GUI checkbox opt in. Historical hints schedule *read-only* probes and never grant write permission. Volatile no-files mode does not save history.
5. **Staged jobs.** Workflow controls select an operation but do not immediately launch it; the persistent bottom **Start job** button is the deliberate launch control and becomes **Stop job** while running. Destructive prompts remain at the action boundary.
6. **Prerequisite preflight.** New `dependencies.py` discovers `smartctl`, Sleuth Kit utilities and `e2fsck`. GUI explains missing optional capabilities. A Windows user may explicitly approve installation of `smartmontools.smartmontools` through WinGet; it does **not** silently install software, download arbitrary executables, or imply that missing SMART data equals healthy SMART.
7. **Desktop usability.** Larger notebook scrollbars, mouse-wheel scrolling, less intrusive idle dashboard/log in debug mode, clearer drive identity/unknown status, and explicit acknowledgment when choosing a volatile RAM backend with no monitored UPS/battery telemetry. A checkbox does not establish protection against crashes or power loss.
8. **Documentation/packaging.** Added `docs/ADAPTIVE_SCANNING_AND_SETUP.md` and updated relevant README, changelog, security and packaging/CI references.

## Verified execution

| Verification | Result |
|---|---|
| Full GUI-enabled `unittest` suite (`xvfb-run`) | **250 passed, 3 skipped** (253 total) |
| Packaged GUI workflow tests | **10/10 passed** |
| Full synthetic scan using packaged `.pyz` | **PASS** (40 MiB, adaptive 1/2/4 MiB requests) |
| Synthetic multipass rescue with packaged `.pyz` | **PASS** |
| GUI synthetic image recovery | **PASS**, output bytes matched source |
| Git patch `git apply --check` against exact user ZIP snapshot | **PASS** |
| Source ZIP checksum/integrity | **PASS** |
| Physical Windows USB-dock scan and in-place write | **NOT TESTED** |
| Hardware-rescue competitive benchmark | **NOT PROVEN** |
| Native Rust compilation and BIOS/UEFI boot qualification | **NOT PROVEN** |

The specific new synthetic/fault-injection tests cover Windows error 1117 vs `errno=22`, continuing past isolated failed reads, read-size adjustment, bounded deferred recovery, accurate unknown-range accounting, fatal access errors, repair-batch limits, local anomaly-history privacy, prerequisite detection and explicit setup approval.

## What this version **does not** claim

- It does **not** automatically alternate an entire disk's scan/repair in repeated batches until complete. It can scan with adaptive deferred I/O and make bounded repair decisions; further interleaved scan/repair cycles are planned, not certified.
- It does **not** prove any improvement in real hardware throughput. The dynamic read-size policy must be benchmarked on actual HDDs, SSDs, USB bridges, and failing samples.
- Successful readback does not establish pristine bytes without trusted reference hashes or redundancy.
- It does **not** automatically overwrite sectors that cannot be read, or silently disable mounted-device and identity safety checks.
- A volatile RAM journal is not a disk backup or crash-recoverable journal. An UPS checkbox cannot certify that the dock, storage and OS survive all interruptions.
- Python remains the running desktop scanning implementation. The Rust recovery crate, legacy boot path, Windows destructive writes, device firmware operations, modern native installers and widespread cross-platform support remain independent engineering/release gates.
- No public-release safety certification, competitive superiority, or forensic chain-of-custody certification is established by these tests.

## Windows field validation recommended

1. Before operation, run the newer GUI and verify it lists the intended device by model, capacity and identifier. Do not assume `windows:PhysicalDrive2` remains the same device after reboot or reconnect.
2. Select **Full scan** but ensure no operation begins until clicking **Start job**.
3. On an expendable test HDD, confirm the adaptive pass continues **after** an isolated WinError 1117, marks skipped regions UNKNOWN and returns for bounded smaller reads. Capture SMART, USB/Event Viewer events and power/bridge details.
4. Confirm scanner read-size transitions and compare scan duration on healthy portions against the fixed-size baseline; control USB enclosure, cable, temperature and caching.
5. Re-run quick triage with anomaly history opt-in and confirm known trouble regions get investigated first. Validate file metadata is not saved in history.
6. Verify a missing `smartctl` is detected and installation requires explicit approval. Do not proceed with destructive writes if the device is failing or its data is irreplaceable.
7. Run destructive interruption tests **only** on sacrificial media after independent review of correct drive-identity and journal failure behavior.

**Release recommendation:** suitable for private/synthetic testing and controlled read-only hardware validation. Do not advertise as public-beta-qualified for unattended in-place repair on valuable drives until physical testing, security review and cross-platform validation pass.
