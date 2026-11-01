# Findings remediation — 20261101T203616Z

Source export: `C:\Users\commstech\Downloads\findings-20261101T203616Z.json`

## Scope

| Repo | Count | Disposition |
|------|------:|-------------|
| `commstech/DriveRepair` | 64 | Validated below |
| `nettech/Repository-Detective` (and other non-DriveRepair rows) | remainder | **Ignored** — out of scope for this tree |

Safety gates were not weakened. No nettech code was modified.

## DriveRepair dispositions

| Rule / finding | Path | Disposition |
|----------------|------|-------------|
| `LINT-RUFF-F401` unused `PowerGuardError` | `desktop/driverepair_desktop/cli.py:39` | **Fixed** — catch `PowerGuardError` on `ram-journal-check` and ramdisk refresh preflight; re-raise as clear `RuntimeError` |
| `LINT-RUFF-E741` ambiguous `l` | `desktop/driverepair_desktop/media_refresh.py:511,:825` | **Fixed** — verified renamed to `offset` / `length` / `latency` (no `\bl\b` remains) |
| `LINT-RUFF-F541` empty f-string | `desktop/driverepair_desktop/refresh_display.py:220` | **False positive / stale** — current line 220 has no f-string; file has no placeholder-less f-strings |
| `REL-INTERNAL-INFRA-REF` `ups@localhost` | `desktop/driverepair_desktop/power_guard.py:79` | **Fixed** — `LOCAL_NUT_HOST = "127.0.0.1"`; still local-only NUT (name charset gate unchanged); test asserts `upsc name@127.0.0.1` |
| `LINT-RUFF-F401` unused imports (`json`, `os`, `patch`, `Mock`, `SimpleNamespace`, `Path`, `Protocol`) | tests + `recovery.py` / `filesystem_repair.py` / `benchmark.py` | **Fixed** — removed remaining unused imports this pass; `Path`/`Protocol`/`os`/`Mock` already absent on current tree (prior remediation) |
| `LINT-RUFF-E702` / `E701` multi-statement lines | `test_catalog_cli_integration`, `test_tsk_recovery`, `test_forensics`, `test_offline_recovery` | **Fixed** — split onto separate lines |
| `LINT-RUFF-E731` lambda assignment | `desktop/tests/test_offline_recovery.py:22` | **Fixed** — replaced with nested `def run_fake` |
| `HEALTH-TECH-PHRASE` | `desktop/driverepair_desktop/recovery.py:34` | **False positive** — docstring / `.pending` journal naming, not TODO/FIXME; no debt markers present |
| `HEALTH-RETRY-NO-BACKOFF` | `desktop/driverepair_desktop/recovery.py:184` | **Fixed** — intentional first-pass no-backoff comment retained; targeted `--retry-missing` keep 5 ms settle delays between binary-split halves |
| `HEALTH-RETRY-NO-BACKOFF` | `src/repair/recovery.rs:57` | **Deferred / prior fix** — Rust path already sleeps via `delay_for_attempt` from earlier remediation; not re-touched this pass |
| `HEALTH-PY-NO-TEST` filesystems package | `desktop/driverepair_desktop/filesystems/…` | **Fixed** — extended `test_filesystems_recover.py` (exFAT detect, raw-device reject, filesystem-mode recover) |
| `HEALTH-PY-NO-TEST` `desktop/…`, `desktop/driverepair_desktop/…`, `scripts/…` | package roots / scripts | **Deferred** — desktop suite covers library code; ops scripts are launchers, not units |
| `SEC-HARDCODED-SECRET` in tests | `test_recovery.py`, `test_large_images.py`, `test_last_resort_system_refresh.py` | **False positive** — test/fixture tokens and paths only |
| `HEALTH-LARGE-FILE` | `cli.py`, `media_refresh.py` | **Deferred** — intentional CLI/refresh surface; split would be a large refactor |
| `QUAL-DEBUG` CLI progress/status prints | `desktop/driverepair_desktop/cli.py` (many) | **False positive deferred** — intentional operator UX / progress, not leftover debug |
| `GRAPH-ORPHAN-FILE` `.gitignore` / `LICENSE` / `.gitattributes` / package `__init__` / rust entrypoints / anchors | various | **False positive deferred** — config, license, package init, and build entrypoints are not import graphs |
| `GRAPH-ORPHAN-FILE` `console_ui.py` | `desktop/driverepair_desktop/console_ui.py` | **False positive** — imported by CLI as `console_ui` |
| `GRAPH-SUSPICIOUS-ISLAND` | `src/repair/recovery.rs` | **Deferred** — informational; Rust recovery module is intentional |

## Verification

```text
cd desktop && python -m unittest discover -s tests -q
```

**Result:** `Ran 159 tests in 27.782s` — **OK (skipped=11)**.
