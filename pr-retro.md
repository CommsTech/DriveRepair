# pr-retro.md — DriveRepair PR retrospective (2026-11-21)

Retrospective for the CI/type-fix validation push and the follow-on reliability
work, commit range `608f4338` (merge base) → `928d669` (tip).

## Scope of the review

| Commit | Subject | Highlights |
|---|---|---|
| `940c6e4` | Fix CI pipeline, WSL path tests, mypy gate, lint issues | Rust toolchain pin refresh ×6, pytest==8.4.2 in CI, 230→0 mypy errors across 29 files, 55→0 Ruff errors |
| `4d7f911` | Add read-only Windows access preflight and storage reliability counters | `inspect-windows-access`, scan fail-closed preflight, native counter supplement |
| `928d669` | Make `python -m driverepair_desktop.cli` behave like the CLI | `__main__` guard + runpy regression tests |

## What went well

- **Gate before freeze.** The rule "mypy must pass before the commit" caught a
  real gap (230 errors) instead of trusting a green-looking local run.
- **Fixture discipline.** All mypy repairs stayed bounded to source changes with
  20 targeted per-line `# type: ignore` entries for Windows ctypes typeshed
  gaps; no mass suppression.
- **Fail-closed behavior proved live.** The Windows node run of
  `inspect-windows-access` returned a structured `WinError 5` report with
  `writes_performed: false` and exit 2 — the fail-closed path is not just a
  documented contract, it was observed in the field.
- **CI modernization stuck.** `dtolnay/rust-toolchain` pinned by SHA in 6
  places; `desktop-tests` moved to pytest because the suite contains
  pytest-only modules (unittest discovery silently skipped them).

## What went badly

- **Lint debt found late.** 55 Ruff errors surfaced only after the mypy push.
  Discovering E701/E702/F401 issues after type work wasted a cycle. The lint
  gate must run before type work, not after.
- **Full-suite discovery stalls on the Linux host.** `python3 -m unittest
  discover` repeatedly hung in host I/O (jbd2 wait during fsync-heavy tests).
  We leaned on bounded suites (7+41+24 tests) instead. The host-side stall is
  an environment problem, but nothing in the repo communicates which suites
  are safe to run on a busy host.
- **Gitea CI is a black box.** API endpoints return HTTP 404, so CI status
  cannot be queried programmatically; "monitor the next CI run" remains
  unverified rather than confirmed.
- **GitHub mirror is unauthenticated.** `gh auth status`: not logged in; no SSH
  key registered; HTTPS/proxy push produced no output. Gitea-as-primary works,
  but the mirror claim is `NOT_PROVEN`, not partial.
- **Silent-CLI footgun shipped for releases.** `python -m
  driverepair_desktop.cli` exited 0 with no output because `cli.py` lacked an
  `__main__` guard. Anyone following the obvious invocation got a lie. Only
  discovered by hands-on validation, not by tests or docs.

## Lessons → rules

1. Run Ruff before mypy in every repair cycle; cheap errors first.
2. Any CLI entry surface (`python -m x.cli`) needs an entry-behavior test, not
   only a documented entry point.
3. A "monitor CI" step without CI API access is not a done step; rename it
   "CI status unqueryable (API 404)" or fix access first.
4. Fail-closed safety must be demonstrated by running the blocked path, not
   only by reading the guard code (evidence: 20261121020831-a0c82ad3 run log).

## Verification state at tip

- Codecraft gate: PASS; mypy: clean; Ruff: clean.
- Bounded suites: 27 regression tests OK on Linux; 7 new access/reliability
  tests OK; Windows node full pytest suite revalidated as recorded in `tdd.md`.
- Windows live preflight: `raw_access_denied` (non-elevated), smartctl present
  but SMART open-failed (bit 2), health `windows_health_limited`, zero writes.
