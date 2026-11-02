# Findings remediation — 2026-11-02

Source: `findings-20261102T013909Z.json` (200 findings across 3 repos).
DriveRepair subset: **101** findings; **47** open+unsuppressed at export time.

## Fixed in this cycle

| Fingerprint / issue | Action |
|---|---|
| `rd-052bf93b79aaf85d` / #97 | Removed unused `rescue_reader` import from `cli.py` |
| GUI scan STARTING freeze | Scan/benchmark/refresh now emit `--progress-jsonl`; GUI wires progressive jobs |
| Ruff E702 in `test_gui_workflows.py` | Split semicolon one-liners |
| Unused `os` in integrity/rescue dashboard tests | Removed |

## Already resolved / stale on `main`

| Finding | Notes |
|---|---|
| #92 unused `pathlib.Path` in `integrity.py` | Already absent on main |
| #80 unused `PowerGuardError` | Still used in `cli.py` (false positive / stale) |
| #81 internal infra ref in `power_guard.py` | `LOCAL_NUT_HOST = "127.0.0.1"` only — local loopback, not a leaked hostname |
| E741 ambiguous `l` in `media_refresh.py` | Not present at reported lines on current main |
| F541 empty f-string in `refresh_display.py` | Not present at reported line |

## Deferred (not release blockers)

- HEALTH-PY-NO-TEST package-level test-gap heuristics
- HEALTH-RETRY-NO-BACKOFF on intentional bounded recovery retries
- HEALTH-LARGE-FILE on `cli.py` / `gui.py` / `media_refresh.py`
- Low-confidence SEC-HARDCODED-SECRET hits inside synthetic unit-test paths
- Remaining info-level style nits already clean under current ruff F401/E741/F541 sweep

Re-scan with Repository Detective after merge; close fingerprints that disappear.
