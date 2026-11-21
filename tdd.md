# tdd.md — DriveRepair TDD cycle record (2026-11-21)

Record of the test-first work in this cycle. Rule used: a behavior fix without
a failing test written first is not a fix, it is a change.

## Cycle 1 — `python -m driverepair_desktop.cli` silent success

**Defect.** `python -m driverepair_desktop.cli --help` exited 0 with no output.
`cli.py` had no `__main__` guard; only `driverepair_desktop/__main__.py`
(importing `cli.main`) worked. Found during hands-on Windows validation, not by
any test.

**Red** (`desktop/tests/test_cli_module_entry.py`, written before any fix):

- `test_module_as_main_prints_help_and_exits_zero` — runpy
  `run_module('driverepair_desktop.cli', run_name='__main__', alter_sys=True)`
  with `sys.argv=['...cli.py','--help']`, asserts `SystemExit(0)` and
  `usage:` on stdout. **Failed**: no SystemExit raised.
- `test_module_as_main_bad_flag_exits_two` — unknown flag asserts
  `SystemExit(2)`. **Failed**: silent exit.
- `test_package_entry_still_uses_cli_main` — `__main__.py` must still wire to
  `cli.main`. Passed and locked the existing good path.

Result: 2 failures / 1 pass — the defect was reproduced by test.

**Green.** Added at the end of `cli.py`:

```python
if __name__ == "__main__":  # python -m driverepair_desktop.cli
    main()
```

`run(argv=None)` already defaults to `sys.argv[1:]`, so no signature change.

**Verify after green:**

| Check | Result |
|---|---|
| `tests.test_cli_module_entry` | 3/3 OK |
| Bounded regression (`test_cli`, `test_b21_scan_followup_wsl`, `test_windows_access_reliability`, `test_windows_native`) | 27/27 OK |
| `mypy --ignore-missing-imports driverepair_desktop/cli.py` | Success, 1 file |
| `ruff check` cli.py + new test | All passed |
| Codecraft gate `--path <repo>` | PASS |
| Windows node, full `pytest` at tip | see below |

Committed and pushed to Gitea at `928d669`.

## Prior cycle carried forward (context, `4d7f911`)

Same rule applied to the Windows access/reliability feature: 7 tests in
`test_windows_access_reliability.py` written against counter supplementing,
identity matching (exactly-one `Get-PhysicalDisk`), and redaction, before the
implementation landed. Windows live evidence: non-elevated
`inspect-windows-access` returns `raw_access_denied`, `writes_performed: false`,
exit 2 — the fail-closed contract observed, not just designed.

## Known limits of this record

- Full `unittest discover` is host-stalled on the busy Linux machine (jbd2);
  bounded suites were used instead. The Windows full pytest suite is the
  authoritative full-suite evidence and was rerun at the tip.
- The Windows node run is recorded with its run-log id; CI (Gitea) status
  remains unqueryable (API 404), so pipeline-green is NOT_PROVEN, not assumed.
