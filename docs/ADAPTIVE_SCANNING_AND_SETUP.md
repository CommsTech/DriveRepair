# Adaptive scanning, staged recovery and desktop setup

**DriveRepair 0.3.3b7 · Experimental engineering build**

## What changed

1. **Full scans use adaptive sequential reads by default.** Starts at the drive-aware baseline (1–4 MiB), grows up to 8 MiB after sustained successful reads, and reduces requests on repeated difficulties. Sizes are logical-sector aligned. This is an *adaptive heuristic*, not a claim that any one size is optimal for all controllers, drives, caches, or USB docks. Actual throughput improvements require paired hardware benchmarks.
2. **Windows I/O device errors are no longer mislabeled as invalid arguments.** Native `winerror=1117` is an I/O device error even if Python also reports `errno=22`. It does not establish whether the underlying cause is platter damage, firmware, power, USB bridge, cable, or controller.
3. **Continue past isolated errors.** The initial full pass records failed I/O ranges and proceeds to collect more readable data; repeated failure clusters can be bypassed as **UNTESTED**. After the good-data pass, a bounded secondary stage subdivides deferred ranges and attempts smaller reads. Do not repeatedly retry a distressed area before reaching the good media beyond it.
4. **Bounded incremental target sets.** When scan evidence identifies more than the allowed repair-region budget, only one explicit, limited group of independently readable candidates is eligible. The result is `partial_candidates_with_unresolved_data`, includes `remaining_candidate_count`, and does not claim a completed whole-drive repair. A later run re-evaluates any future candidates; physical write verification remains mandatory.
5. **Optional remembered anomaly locations.** With `--remember-anomalies`, DriveRepair writes a compact map of slow, unreadable and skipped offsets to the user's local application-state directory (never the source disk). The file key is derived from drive fingerprint, capacity and sector size. The map contains **no sector data**, file contents or raw serial numbers. Historical hints cause new **read-only** probes; they never authorize writes. RAM-only no-file jobs explicitly reject history persistence. No history is saved without opt-in.
6. **Staged desktop job launching.** Workflow buttons select and prepare a job; the always-visible bottom **Start job** button launches it. During an active job this same control becomes **Stop job**. Repair authorization, drive identity confirmation, and volatile-memory risk prompts are still required when beginning a write-capable operation.
7. **Startup prerequisite status.** Detects smartctl, Sleuth Kit fls/icat, and e2fsck locally. Missing tools are shown as unavailable, not as healthy or failed disk measurements. On Windows, if WinGet is installed, a user-approved **Install SMART tools** action invokes the exact `smartmontools.smartmontools` package ID through the OS package manager. No automatic third-party binary downloads or silent elevation.
8. **Improved window usability.** Wider scrollbars, mouse-wheel notebook scrolling, no forced debug-console/dashboard expansion at startup, and an informative selected-drive banner. Unknown health remains unknown rather than appearing as a fabricated media/mechanical finding. In-place refresh offers an explicit volatile-RAM no-telemetry acknowledgment; tmpfs journal mode still requires verified compatible power monitoring.

## Operational guidance for the Seagate USB example

The repeated failed full-scan request near byte offset `77,561,069,568` showed **Windows native error 1117**. This confirms an I/O device error, not necessarily a physically defective disk sector. Run **Investigate a failed offset** (read-only) to determine whether smaller aligned requests work. Before another physical rewrite, check the external dock's power, USB cable, Windows Event Viewer storage/USB errors and the manufacturer's SMART attributes if available. A high read-error rate, changing disk identity or unavailable device still requires stopping.

A full scan can stress an already failing disk. For irreplaceable data, prioritize image-first rescue to separate storage. Auto-tuning is a performance heuristic and never makes physically unstable hardware reliable. Writing back repeatably read bytes is not a means to reconstruct unrecoverable or silently corrupted data.

## CLI examples

```powershell
python DriveRepair-0.3.3b7.pyz list --json
python DriveRepair-0.3.3b7.pyz scan --device windows:PhysicalDrive2 --mode full --adaptive-io --ack-risk --json
# Optional private weak-region history; no sector content is saved:
python DriveRepair-0.3.3b7.pyz scan --device windows:PhysicalDrive2 --mode triage --remember-anomalies --json
```

**Never assume the example device ID refers to your intended drive.** Run `list --json`, match the physical model, size, identity and current system topology first. The diagnostic scan never writes; guided in-place refresh remains an explicit high-risk operation with separate authorization.

## Accuracy and safety limits

- A successfully read block is **not cryptographically verified file data**. Correctness requires trustworthy baseline hashes or a good redundant copy. Equal repeated reads establish repeatability only.
- Deferred retries are limited. If a large area cannot be recovered within the budget, its bytes stay **UNKNOWN**. The scan map must not color skipped regions green.
- A local anomaly map is not an image and cannot recover previously lost data. Deleting history does not change the patient disk. Opt-out by omitting `--remember-anomalies`.
- The RAM-only backend holds only the in-flight region and does not survive program, host, power or dock failure; it is not a backup, and no UPS checkbox changes that.
- The portable desktop build requires Python 3.10+ and Tk. The Rust core and experimental boot firmware remain separately qualified work. No claim of native Windows/macOS physical-write certification or firmware flashing is made.
- The Windows installer option requires explicit user confirmation and the machine's supported package manager. For Linux/macOS, follow official OS distribution packaging for smartmontools.
- **No published benchmark superiority or hardware reliability guarantee** is established by synthetic tests. Real-drive validation, Windows hardware fault injection and read/write power interruption studies remain release gates.

## Release validation

Synthetic tests cover WinError 1117 classification and continuation, read-size growth, fatal access errors, bounded repair batches, source-write count zero during scans, and privacy-limited anomaly history. GUI tests cover all guided tabs, staged image scan and recovery, and byte-identical recovered image output. See `desktop/tests/test_adaptive_scan.py`, `test_dependencies.py`, and `test_gui_workflows.py`.

External technical references: [GNU ddrescue 1.30 manual](https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html), [Microsoft system error codes 1000–1299](https://learn.microsoft.com/windows/win32/debug/system-error-codes--1000-1299-), and the [smartmontools project releases](https://github.com/smartmontools/smartmontools/releases).
