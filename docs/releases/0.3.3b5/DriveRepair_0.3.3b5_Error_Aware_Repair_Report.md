# DriveRepair 0.3.3b5 — error-aware guided repair and dashboard

**Status:** private engineering candidate, not qualified for production physical-drive writes. 2026-11-01.

## Why prior repairs stopped

The guided scanner uses `max_errors=16`. Once the read-error budget was reached, the scanner returned `aborted_error_limit`, and the prior planning code treated any incomplete scan as a global write veto. That prevented work on independently verified candidate regions. The read-only scan UI reported a generic exit code 2; some SMART-independent heuristics also labeled repeated read errors as *mechanical FAIL*, without evidence of mechanical failure.

## Changes made

- `guided_repair.py`: accepts the **read-error budget stop** as a reason to proceed to bounded read-only investigation of *known* failed offsets. Records that unvisited media remains unknown and mandates a partial result. Distinguishes that from fatal device/access interruptions, which continue to block writes.
- `guided_repair.py`: splits failing reads to sector-aligned subregions; requires two identical reads for each potential candidate; quarantines unreadable, disagreeing or repeat-probe-failed subregions. A third read by the journaled writer must agree before any rewrite, and a post-write readback verifies the rewritten data. Repeatable bytes are **not** necessarily historically correct bytes.
- `scanner.py`: retains offsets for failed repeat-probes so unrelated, confirmed readable chunks can proceed without falsely treating all sectors as defective.
- `health.py`: read errors alone no longer imply confirmed mechanical or USB-transport failure. SMART alarms, disconnect/access loss, device identity changes and other critical conditions remain blockers.
- `cli.py`: accepts bounded investigation after read-error limit; reports `partial_repair_unresolved_data` for partial results or `recovery_required` when no safely rewriteable regions exist. These are **not full-success states**.
- `gui.py`: workflow status distinguishes partial repair and needed rescue, not only generic `ERROR 2`; live metric cards use bytes read, read-error counts, observed speed and scan ETA, then rewrite/verify totals for actual repair. Color swatches identify **Not scanned**, **Read successfully**, **In progress**, **Slow region**, **Needs investigation**, and **Read error/unknown**.
- Updated README, CHANGELOG, and `docs/ERROR_AWARE_REPAIR.md` with behaviors and limits.

## Validation

- `xvfb-run -a python -m unittest discover -s tests -v`: **231 tests run; 228 passed; 3 skipped** (Linux platform-specific skips).
- Ten dedicated GUI/navigation/metrics tests passed in a real Tkinter window under Xvfb.
- Synthetic fault tests cover a stopped scan with recoverable and unrecoverable subregions, partial writes, persistent error quarantine, mismatched rereads, disconnect during investigation, and truthful partial outcome.
- `scripts/build_desktop.py`: passed; compiled Python modules, built `.pyz` and wheel.
- Packaged `.pyz` smoke test: scanned 1 MiB generated image with no repair candidates; returned `completed_no_refresh_needed` with **no journal created**.
- Source patch verified with `git apply --check` against the DriveRepair 0.3.3b4 packaged source; exact changed-file content matched.
- **No physical disk read or write was performed; no Windows-specific hardware, Rust compiler, BIOS or UEFI boot tests were performed in this cycle.**

## Important limitations

1. On a genuinely unreadable, inconsistent or checksum-unknown sector, there may be no correct original bytes to write back. No speculative bit flipping is permitted.
2. Destructive reinitialization of truly unreadable sectors (zeroing to attempt firmware relocation) remains **NOT IMPLEMENTED**. It needs independent, explicit data-loss authorization and hardware testing; it cannot restore the lost file bytes.
3. `aborted_error_limit` means **not all sectors were scanned**, including on a full-scan request. Any completed targeted refresh after this is necessarily **PARTIAL**, even if all attempted rewrites read back correctly.
4. A drive with verified critical SMART failure, unstable USB connection or missing identity cannot be made safe by overriding a UI error. Stop writes until the cause is addressed. A RAM-only journal cannot recover after a process/host crash.
5. Readback verification establishes that the rewritten bytes matched immediately afterward, not the absence of latent corruption, recovered file integrity or restored mechanical life.
6. Do not run physical in-place writes on a drive holding the only copy of irreplaceable data. Use validated imaging/professional recovery as appropriate.

## Install / test

```powershell
python .\DriveRepair-0.3.3b5.pyz gui
```

Choose **Diagnose / Rescue**, select the external disk by model, capacity and identity, and choose **Quick repair** (bounded triage) or **Full repair** (surface scan subject to a safety error limit). Default Balanced policy investigates error offsets; Preserve policy only considers slow consistently readable regions. When SMART health is uncertain or warning, explicit additional authorization is required. Keep unknown regions untouched. For image-only regression tests:

```bash
cd desktop
python -m unittest discover -s tests -v
```

**Recommended next hardware gates:** Windows USB dock over SATA and USB bridge, 512e/4Kn, disconnect/reconnect before writes and mid-write, forced process shutdown during RAM journal, stable sector identity, real SMART failure and actual read error scenarios, interrupted journal resume, controlled comparator tests. Public beta for physical writes must wait for this evidence.
