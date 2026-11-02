# DriveRepair 0.3.3b12 — Engineering verification and release disposition

**Baseline:** `DriveRepair-main(20261102-194249).zip` (uploaded 2026-11-02)  
**Status:** Private experimental engineering build. No production physical-write qualification.  
**Verification environment:** Linux/Python, synthetic regular-image and mock-device tests; **not** a Windows USB dock.

## Inputs and reproduced concerns

The provided Qt screenshots show Full Repair stuck at approximately 8.4% while investigating errors and a Stop button that does not end the guided write-capable job. The uploaded console log shows a `QFont::setPointSize` warning; the Qt debug log records a Windows storage-inventory failure after `Get-Disk`, CIM and WMIC timed out. Those logs do **not** record sufficient per-read events to establish which exact kernel read was outstanding at 8.4%.

**Confirmed code defect:** In `investigate_failed_ranges`, `read_calls` was incremented after successful low-level `read_at` operations. An `OSError` therefore did not consume the retry budget, even when repeated recursive splits generated thousands of small failed reads. The 0.3.3b12 version increments before every read, emits an `investigation_state` before read access and reports the number of attempted calls and elapsed time. The elapsed limit is best effort: a single Windows raw I/O can still block beyond a Python deadline.

**Confirmed usability defect:** Qt refused to stop any guided Fix job because the process could potentially be writing. It now uses a private local `STOP` stdin command and a cooperating engine that checks stop requests between reads or at committed write transaction boundaries. User-visible status explicitly says that a read stuck in the USB driver may not be cancellable promptly.

## New implementation

- Separate Qt bars for **current phase** and **estimated overall job**; guided scan, investigation and refresh are visibly distinct. The overall 60/15/25 phase weights are estimates, not actual unique LBA coverage or a guarantee that repairs will be scheduled. A completed job shows 100% of the planned work, not proof of drive health.
- Investigating-phase events expose current offset, request length, attempted read count, attempt budget, and read state; Qt debug mode periodically persists `IO_TELEMETRY` evidence. If updates stop, the GUI displays the last request and elapsed seconds without an I/O result.
- Qt Stop requests cooperative cancellation for write-capable workflows. The targeted journal engine checks stop only **between complete transactions**. Standalone read-only operations use a bounded terminate/kill approach after a grace period. Neither can guarantee cancellation of a blocked kernel operation.
- Media-aware logical rewrite caps: detected SMR = 256 KiB and up to 16 selected transactions; reported SSD/NVMe = 128 KiB and up to 16; CMR/generic = 1 MiB with existing budget. UI displays profile evidence and limitations. These are risk-limiting **logical** transaction sizes, not the physical zone, NAND erase-block or SMR band geometry.
- New tests exercise failed-read budget accounting, stop before I/O, stop between verified transactions, and separate phase/whole-job progress calculations.
- Updated docs, package version, and stale build script/CI artifact references.

## Validation executed

- `PYTHONPATH=desktop python -m unittest discover -s desktop/tests -q`: **292 run, 288 passed, 4 skipped**.
- New fault injection: **5/5 passed**.
- `scripts/build_desktop.py`: Python test run, compileall, portable PYZ build, Python wheel build and CLI help smoke test all passed.
- `care-image --help` confirms the private `--cooperative-stop-stdin` option is in the portable package.
- Patch applied to a clean extraction of the exact uploaded ZIP, followed by byte-for-byte comparison of all **14** modified/added source paths.
- Bootable BIOS/UEFI builds and Rust crates **not built** (Rust toolchain unavailable in the environment).
- Native Windows/PySide6 clickthrough, USB-dock behavior, real head/flash read errors, and physical write interruption **not tested** (PySide6 not installed, hardware not accessible).

## Safety interpretation

A successful rewrite and readback compares data against bytes the disk just returned; it cannot prove historical correctness or recover irrecoverably lost user data. USB transport errors and Windows I/O errors alone do not prove physical media damage. Logical left/right sector neighbors are **not** necessarily physically adjacent on SMR or SSD media. SMR internal write amplification and SSD wear leveling remain controller-managed; no firmware modification is implemented. Reusing the in-memory RAM journal after a process/power crash is impossible.

Windows' repeated `Get-Disk` timeouts **remain unresolved** on the user's host. Native advisory queries do not prove boot/system-device exclusion; DriveRepair must keep physical writes disabled when identity verification is unavailable. The unrelated `QFont::setPointSize(-1)` message is visible in the user's logs but no definitive root cause is established by these code changes.

## Next hardware acceptance gates

1. On a disposable USB SSD, trigger an unreadable mock/fault-injected region and confirm `IO_TELEMETRY` includes the active offset and stops after the read budget. Validate Qt interaction and stale-event behavior.
2. With a separate durable journal on healthy storage and a sacrificial disk, press Stop during reading, during an active write, and after a verified transaction; prove that committed data and resumable state remain correct.
3. Repeat on a manufacturer-confirmed SMR and independent CMR disk and compare latency, errors, write amplification, temperature and SMART trends without claiming restored reliability.
4. Isolate Windows storage discovery delays from USB controller faults. Never bypass identity checks to gain write access.
5. Validate the full scan→investigate→repair result semantics and phase progress. A true repeated scan/repair/reassess autonomous loop remains future work and is **not** included here.

**Change control:** No hardware operated, firmware changed, repository pushed, or production auto-repair enabled.
