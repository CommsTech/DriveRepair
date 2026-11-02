# DriveRepair 0.3.3b10 — Engineering report

**Based on:** `DriveRepair_0.3.3b9_Qt_Workstation_Source.zip`, not a live Gitea checkout.  
**Scope:** UI, measurement integrity, read-only drive inspection, recovery-state continuity and firmware architecture safety.  
**Disposition:** **Experimental engineering candidate — NOT approved for public physical-drive repair or firmware manipulation.**

## Root cause analysis from November 2 Windows screenshots and logs

1. **False Quick Scan progress:** Qt used a fraction (completed probes / planned probes) as a percentage. Thus 100% of Quick Scan could appear as `1.0%`. Corrected and regression-tested with a dependency-free percentage helper.
2. **False surface-map reassurance:** Each cell represented ~1/384 of the disk, but *any* readable 8–16 MiB sample turned the entire multi-gigabyte cell green. The new stable byte-coordinate map colors only the verified fraction within each cell. Red and orange are error/latency observation markers, not whole-cell diagnoses. Repeated reads do not inflate coverage.
3. **Quick Scan scope/sampling:** Guided Quick Repair had 10% distributed strata, while the Qt read-only Quick Check still used a tiny default 128 × 1 MiB. Both Qt quick operations now plan >=10% of the whole disk. Random seeds are recorded; within bounded groups, reads retain some locality to limit rotational seeks. Neither sampling nor successful reads prove data integrity or drive health. Sampling may take more than 10 minutes on 1 TB.
4. **Speed/ETA semantics:** Qt now labels recent throughput separately from job average and shows an operation-specific ETA. A refresh percentage is derived from its *repair transaction queue*, not from the byte offset of its last write. The reported observed decrease from 120+ MiB/s to lower figures cannot be attributed to the GUI without controlled measurements: logs show very slow media/transport operations, Windows I/O error 1117, and a USB disconnect. ETA is not guaranteed when drive I/O stalls.
5. **Windows identity timeouts:** `Get-Disk -Number 2` can hang on an unstable USB/storage stack. A new **read-only** native Win32 property probe uses `CreateFileW` with `GENERIC_READ` and `DeviceIoControl(IOCTL_STORAGE_QUERY_PROPERTY/IOCTL_DISK_GET_LENGTH_INFO)` to inspect bus, reported model/firmware, logical/physical sector size and disk length. It runs as a separate child process via the Qt Drive Details control. **It cannot establish IsBoot/IsSystem and is NOT used to authorize writes.** The blocking PowerShell identity check remains a release blocker for Windows write paths. Bridging this safely requires additional independent boot/system volume verification and physical-device fault tests.
6. **Reconnect:** Full read-only scans (and opted-in Full Repair scanning phases) can save a metadata-only checkpoint and the Qt app can poll for the same drive and request read-only resume. Resume still requires a fresh OS disk identity; no physical write automatically restarts. A RAM-only write cannot restore its in-flight original data after power/process failure. The GUI now also offers a durable journal on another healthy disk and a manual existing-journal resume mode, still subject to physical-drive safety checks.
7. **GUI discoverability:** Fix / Recover / Check goals filter operations instead of presenting every tool together. Added contextual info buttons, rich tooltips and a Drive Details action. The existing legacy Tk toolkit remains available while Qt reaches feature parity.

## OS evidence leveraged

| System | Read-only observation | Important limitation |
|---|---|---|
| Windows | Storage descriptor, disk geometry, firmware revision reported by controller/USB bridge; Windows Storage management for independent boot/system checks | USB bridge may spoof or omit media properties. Direct IOCTL does not authorize writes. Disconnected drives can block driver requests. |
| Linux | `/sys/class/block/<name>/queue`: rotational, zoned, logical/physical sector sizes, maximum sectors, discard limits, optimal I/O | Queue limits are OS request limits and may represent a USB bridge; they are not proof of CMR/SMR or data integrity. |
| macOS | `diskutil info -plist` for whole-disk identity, protocol, media and SMART status when exposed | External USB storage frequently hides SMART, firmware and physical recording features. |

The OS inspector is informational. It does not modify firmware, SMART logs, partitions or sectors and does not broaden the physical write authorization policy.

## Firmware architecture and neural reconstruction assessment

The Rust `firmware_inspect` module provides a **vendor hint / read-only privilege trait**, intentionally not any vendor command transmitters. Matching `ST`, `WDC` or `TOSHIBA` strings is not sufficient to determine a board generation, service-area module map or safe recovery sequence. No firmware flashing, ATA VSC, serial TTL motor operations, NVMe panic/bootloader modes, FTL bypass, SMART log clearing or translator rebuilding are implemented. Future support needs hardware-family/revision/transport-specific documentation, manufacturer firmware provenance, signed test fixtures, independent readback and destructive sacrificial tests. USB passthrough may not expose these interfaces at all.

Neural classification is a legitimate research direction for **triage on recovery image copies**. Predicted or synthesized bytes must never be represented as recovered originals or written to the patient disk. No untrained CNN/Transformer, hallucinated JPEG/SQL file repair or speculative sector patching was added.

## Validation evidence

- Python unit + integration suite: **274 executed, 270 passed, 4 skipped** on Linux. The skips include Qt/platform-dependent tests; PySide6 was not available locally.
- Python `compileall`: passed.
- Portable Python zipapp and installable wheel: build passed, CLI entrypoint passed.
- Packaged CLI scan: passed on a synthetic 64 MiB image using randomized triage, with 12.5% unique coverage, zero observed read failures and a recorded seed.
- Image tests perform no physical media writes.
- Git patch: applied cleanly to the exact 0.3.3b9 ZIP and verified against the updated source file-for-file.
- Windows native read-only descriptor parsing: synthetic tests only. Actual Win32 ioctl behavior **not tested** here.
- Rust module: source included and CI-facing tests authored; **not compiled locally because Cargo/Rust were unavailable**.
- Qt UI source compiled by Python, but **no native PySide6 clickthrough**: attempts to install PySide6 failed because the build container has no network/package access.
- No firmware writes, destructive tests, Windows USB dock writes, GUI disconnects, BIOS/UEFI boots, or competitive benchmark results were observed here. No code pushed to Gitea.

## Hardware acceptance gates before public beta

1. On a sacrificial Windows machine and USB dock, test `inspect-storage` and compare results against smartctl/Get-Disk/Disk Management without assuming that the bridge has exposed true media firmware or serial. Address the repeated `Get-Disk` timeout safely; do not bypass system-disk protection to force a physical write.
2. Exercise actual 10% Quick Check on several HDD/SMR/CMR/SSD/NVMe/USB bridges. Confirm sampled byte offsets span the *entire device*, measure unique coverage, speed, error containment and seek overhead. Compare against the previous version and GNU ddrescue with identical conditions.
3. Unplug/replug during read-only full scan and scan-phase Full Repair; verify checkpoint integrity, new PhysicalDrive number handling and non-duplication of completed work.
4. On disposable media only, inject disconnect/power loss during an *in-place write* with a durable journal; verify original region recovery, stable identity, new transport, exact journal state and readback, plus refusal on ambiguous USB serials. **Do not do this with RAM-only on a valuable drive.**
5. Test Qt mouse, keyboard, scaling, tooltips, screen readers, resizing, toolbar and workflow selection on native Windows/macOS/Linux. Confirm progress, map, ETA and error indicators remain truthful.
6. Rust CI test/build, independent security audit, native BIOS/UEFI ISO boot qualification, manufacturer firmware qualification, performance/recovery accuracy benchmarks.

## Primary technical references

- Microsoft [IOCTL_STORAGE_QUERY_PROPERTY](https://learn.microsoft.com/windows/win32/api/winioctl/ni-winioctl-ioctl_storage_query_property), [STORAGE_DEVICE_DESCRIPTOR](https://learn.microsoft.com/windows/win32/api/winioctl/ns-winioctl-storage_device_descriptor), and [IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS](https://learn.microsoft.com/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents).
- GNU [ddrescue manual](https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html): mapfile durability, copying/trimming/scraping/retrying and I/O fault handling.
- Project: `docs/QT_UI_AND_HARDWARE_RELIABILITY_B10.md`, `docs/MEDIA_AWARE_SCANNING_0.3.3b8.md`, `docs/BOOT_RECOVERY.md`, `SECURITY.md`.
