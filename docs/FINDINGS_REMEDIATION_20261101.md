# Findings remediation — 2026-11-01

Source export: `findings-20261101T180217Z.json` (200 rows, mixed repos).

## Scope

| Repo | Count | Disposition |
|------|------:|-------------|
| `commstech/DriveRepair` | 34 | Validated and repaired in this tree |
| `commstech/nettech` | 151 | Wrong-repo for DriveRepair workspace — not modified here |
| `commstech/Repository-Detective` | 15 | Wrong-repo — not modified here |

## DriveRepair repairs (this release)

| Finding | Action |
|---------|--------|
| `LINT-RUFF-E741` ambiguous `l` in `media_refresh.py` | Renamed loop vars to `offset` / `length` / `latency` |
| `LINT-RUFF-F401` unused imports (7) | Removed (`Protocol`, `Path`, `os`, `Mock`, `patch`) |
| `LINT-RUFF-F541` empty f-string at `refresh_display.py:220` | **Stale** on current tree — no empty f-string at that line |
| `SEC-HARDCODED-SECRET` in `test_recovery.py` | **False positive** — replaced test tokens with opaque `test-token-*` IDs |
| `HEALTH-RETRY-NO-BACKOFF` `recovery.py` | Documented intentional no-backoff on first pass; added 5 ms settle delay on targeted retry isolation |
| `HEALTH-RETRY-NO-BACKOFF` `src/repair/recovery.rs` | **Fixed** — `delay_for_attempt` now `thread::sleep`s instead of discarding the delay |
| `HEALTH-PY-NO-TEST` desktop/scripts packages | **Covered / N/A** — desktop suite is 106 tests; ops scripts are launchers, not library code |
| Suppressed QUAL-DEBUG / GRAPH-ORPHAN / TECH-PHRASE | Left suppressed — intentional CLI progress / config anchors |

## Additional audit (this session)

- Unit suite: **106 tests, OK (skipped=2)** after remediation.
- `--confirm-identity` gate covered by failure-path test.
- Live SanDisk 500 GB #3 Adaptive lab (0.2.9b1): write probe OK; Adaptive completed `rewritten_bytes=0` (no slow targets); prior #1/#2 write failures remain hardware/dock-specific.
