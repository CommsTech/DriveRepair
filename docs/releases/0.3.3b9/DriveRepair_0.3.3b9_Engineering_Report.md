# DriveRepair 0.3.3b9 — Qt workstation and interrupted-scan engineering report

**Source:** `DriveRepair-main(20261102-155201).zip` supplied November 2, 2026.  
**Change class:** optional GUI migration, read-only checkpoint/reconnect capability, truthful rate reporting.  
**Safety:** no physical drive was opened or written by this build/test process.

## Findings from supplied evidence

- Source run: adaptive 1 TB full scan reached about **20.04%** address coverage when Windows reported repeated errors (`winerror=1117` for I/O device errors and `winerror=433` after the USB device disappeared). Earlier source progress reached approximately 200 GB of readable data but later identity revalidation did not complete. The tool's result was `repair_blocked_identity_recheck`; that is a valid reason not to write.
- The detected read latency varies wildly: multiple 8–16 MiB requests took seconds; one 16 MiB request exceeded 111 seconds. These observations do not establish whether the fault is platter media, USB bridge, cable, controller, power delivery, or firmware.
- The old Tk speed field labeled `CURRENT SPEED` was often `bytes_done / total_time`, meaning an **average**. Both the CLI guided-scan path and the new Qt client now have recent-window speed handling.
- A read-only full scan had no durable position checkpoint after a disconnect. This release adds a local offsets-only checkpoint. Resume is **manual and identity-checked**, not an automatic or unsafe physical-write restart.

## Implemented

1. `qtgui.py`: optional PySide6 modern workstation; goal buttons, staging, clearly labeled speed/average, responsive subprocess operation, coarse activity map, explicit write warnings, and advanced logs. Existing Tk GUI preserved (`gui-legacy`); default `gui` prefers PySide6 if present.
2. `rates.py`: rolling recent-window throughput tracker. Replaces the ambiguous whole-job average as the scan/targeted-refresh `speed_bps` where supported; `average_speed_bps` remains available.
3. `scan_checkpoint.py` and `adaptive_scan.py`: persistent, size-limited read-only scan checkpoints using atomic writes; full-drive resume verifies hashed model/serial/geometry identity, geometry and saved offset, even if the reported Windows disk number changes. Distinguishes Windows device disappearance (`433`) from media I/O errors (`1117`). It never stores sector bytes or authorizes source writes.
4. `cli.py` and `scanner.py`: `--resume-scan`, `--scan-checkpoint` and new launch options. Scan checkpoints default to private local metadata in normal full read-only scans; RAM-only guided repair remains no-file by default unless the operator explicitly requests a separate metadata checkpoint.
5. New tests and documentation: `tests/test_scan_resume_qt.py`, `docs/QT_WORKSTATION_AND_SCAN_RESUME.md`, changelog, build script and CI version references.

## Validation

| Gate | Result |
|---|---|
| Python source regression | PASS — 258 passed, 4 skipped without graphical display |
| Full regression under virtual X display | PASS — 267 passed, 3 skipped |
| Synthetic disconnect/resume fault-injection | PASS — restart at saved offset, no source writes |
| Checkpoint identity/geometry rejection | PASS |
| Throughput-window arithmetic | PASS |
| Portable `.pyz` build and wheel | PASS |
| Portable full-image scan and resume | PASS — 8 MiB synthetic image, 100% coverage, resume accepted |
| Patch applied against clean supplied baseline | PASS |
| Qt Python code compilation | PASS |
| Native Qt GUI clickthrough | **NOT TESTED** — PySide6 unavailable in build environment |
| Windows USB reconnect and drive ID preservation | **NOT TESTED** — physical dock unavailable |
| Windows/macOS/Linux native Qt packaging/installer | **NOT TESTED** |
| Rust core native compilation and UEFI/BIOS boot | **NOT VERIFIED in this cycle** |
| Physical in-place repair / power-cut testing | **NOT TESTED** |
| Neural file reconstruction and raw vendor firmware writes | **NOT IMPLEMENTED** |

## Design rationale and safeguards

Device firmware service areas, internal SMR translation structures, and NAND mappings are not standardized at a universally repairable level. Linux SG_IO and NVMe passthrough are still mediated by OS drivers. The example vendor-specific CDBs and force-bootloader algorithms supplied as research are not independently proven for the drive models in this repository, so no firmware console or unlock command is enabled.

ML fragment classification can rank file-type candidates and help prioritization on a **forensic copy**, but it is not proof of original file bytes or correct ordering. Generating synthetic content to make a JPEG display is a derivative repair, not exact data recovery; it must never be silently substituted into evidence or raw source sectors. This release intentionally adds no untrained PyTorch network or unvalidated generated-byte patcher.

Qt is used for user presentation only. The CLI remains authoritative for disk identity, physical-write authorization, journal control, and recovery operations. It emits bounded JSON progress messages. Avoid new shared-memory daemons until profiling demonstrates real overhead.

**Cooperative safe-stop remains outstanding:** the Qt UI can terminate read-only I/O (the saved scan progress may be incomplete); it refuses to advertise mid-write termination as safe for experimental physical-repair operations. Implement cancellation at a verified transaction boundary before qualifying forced stop.

## Reproduction commands

```sh
cd desktop
python -m unittest discover -s tests -v
python -m pip install -e '.[qt]'
python -m driverepair_desktop qt-gui
python -m driverepair_desktop gui-legacy
```

Windows read-only full-scan restart, after unplug/replug with current identity:

```powershell
python -m driverepair_desktop scan --device windows:PhysicalDrive2 --mode full --ack-risk --json
python -m driverepair_desktop scan --device windows:PhysicalDrive2 --mode full --ack-risk --resume-scan --json
```

If Windows Storage cmdlets hang or identity changes, the command correctly refuses to continue until discovery works again. If a physical drive contains irreplaceable data, rescue to separate storage or seek professional assistance before additional stress or experimental rewriting.

## Public-beta disposition

**Engineering preview; not approved for unrestricted beta on valuable or mechanically failing media.** Requires verified Qt UI on Windows, native installer, live USB disconnection tests, physical write interruption testing, signed distribution, boot qualification, and independent security review. No claims of firmware 'platter smoothing,' universal controller unlock, perfect bit reconstruction or competitor-beating recovery rates are supported by this test evidence.
