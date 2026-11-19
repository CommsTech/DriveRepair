# Test-first record — SpinRite-class surface recovery (2026-11-19)

## Request

"Use knowledge from https://github.com/morluto/rea to reverse engineer the
techniques of Spinrite and improve upon them and add them to DriveRepair."

## Finding about the cited repository (checked before any code)

`morluto/rea` is REA ("Reverse Engineer Anything"), a generic reverse-engineering
MCP/CLI toolkit (package `rea-agents` 6.9.0: APK/binary/Frida/browser analysis).
It contains **no SpinRite material**:

```
grep -ril 'spinrite' .        -> 0 files
grep -ril 'gibson|grc.com|dynastat|surface scan' -> 1 file (docs/devicetree.md, unrelated)
```

So REA cannot "supply" SpinRite knowledge: it is the instrument, not the data,
and no SpinRite binary was supplied to analyse. What was implemented instead is
an independent engineering port of the behaviours SpinRite's author documents
publicly (GRC SpinRite technology pages): consensus rereads with varied head
position, per-zone adaptive timing baselines, sector-level localisation, and a
verified read-back write path. No proprietary code, strings, or assets were
copied.

## Failing test written first

`desktop/tests/test_surface_recovery.py::ScannerIntegrationTests::test_scan_records_consensus_and_sector_evidence`
was written before the scanner was wired and failed exactly as intended:

```
AssertionError: 'consensus_candidates' not found in {... 'inconsistent_reads': [], ...}
Ran 11 tests ... FAILED (failures=1)
```

The ten unit tests for the new module passed at that point, isolating the
missing integration rather than a broken primitive.

## What changed

New module `desktop/driverepair_desktop/surface_recovery.py`:

- `consensus_read()` — rereads a region at several start positions (head-offset
  variation), aligns each attempt back to the canonical offset, and takes a
  position-wise plurality vote. Reports `agreeing_bytes_pct` and
  `distinct_blocks`; returns data only when coverage is complete and agreement
  clears the floor. Read-only by construction.
- `ZoneLatencyBaselines` — per-zone median/MAD baselines with a global fallback
  until a zone has enough samples. Prevents inner-track slowness being reported
  as marginal while still catching genuine outliers.
- `sector_drilldown()` — bounded per-sector probing inside a failed chunk, with
  even spacing, sector cap, and wall-clock deadline.

Scanner integration (`scanner.py`):

- `compare_suspects` now performs a 3-attempt consensus reread. Any disagreement
  is still appended to `inconsistent_reads` with the existing UNKNOWN wording, so
  guided-repair policy is unchanged; an agreeing majority is additionally exposed
  as `consensus_candidates` labelled candidate-only.
- Failed chunks are drilled down for non-aborted scans, exposing
  `sector_drilldown` and `sector_probe_reads`. Abort paths are untouched, which
  keeps `extra_suspect_reads == 0` abort evidence intact.
- Triage exposes `marginal_probes` from the per-zone classifier.

Not changed: `media_refresh.py` already performs consistency reads and an
unconditional read-back verification after each write ("Always read back: even
--no-verify must detect obvious errors"), which is the SpinRite refresh guarantee.
No write-policy change was needed or made.

## Follow-on defect found by the Windows suite (same session)

Running the full suite on the Windows node exposed a real bug that Linux cannot
see (Tk tests skip there): `test_image_scan_updates_actual_bytes_read_speed_and_eta`
timed out with `['2.00 MiB', '0 observed', 'Measuring…', 'Complete']` — bytes and
ETA settled while RECENT SPEED never left the placeholder. A scan that finishes
inside one `RateWindow` sample never emits `speed_bps`.

Fixed with `rates.choose_speed()` (fall back to the measured average only after
completion, labelled `(avg)`), used by both `gui.py` and `qtgui.py`, plus six
Linux-runnable tests in `tests/test_rates.py`. The first attribution ("harness
race") was wrong; widening the wait kept the diagnostics and the real fix
followed.

Windows result after the fix: full desktop suite `358 tests, OK (skipped=11)`,
with the GUI workflow module passing twice consecutively.

## Evidence

- `python3 -m unittest discover -s tests -p 'test_surface_recovery.py'` → 11 OK
- `test_scanner.py` → 12 OK, `test_triage.py` → 4 OK
- Full desktop suite → see commit message / build log for the run that passed.

Safety: nothing in this change writes, TRIMs, or authorises repair. A majority
vote is evidence about which bytes came back most often, never proof of the
original data.
