# Specialist review — 2026-11-19

Four specialists reviewed `main` at `3e3d9bf` (pre-change): Darwin (competitive
research), Optimization Expert (performance), Software Engineer (code quality),
and Security Specialist (threat model). Each was asked for file:line evidence,
severity, and the smallest safe fix; none were allowed to edit files.

This document records **what was implemented, what was deliberately deferred,
and what was measured**. Deferred items are roadmap, not silently dropped work.

## Implemented in this pass

| Source | Finding | Change | Verification |
|---|---|---|---|
| Security (LOW) | `health.py` fell back to a bare `'smartctl'` PATH lookup, so a planted binary could supply the SMART evidence that feeds repair authorization | Execute only the resolved path; fail closed with an actionable error when no smartctl is found | `test_security_hardening_20261119.py` (3 tests) |
| Security (LOW) | Journal directory could be adopted through a symlink to another empty directory, and kept a world-readable mode | `lstat` rejects symlinks; adopted directories are chmod 0700 on POSIX | same file (3 tests) |
| Optimization (HIGH) | Rescue loop ran `_validate_state` per chunk, re-sorting the whole missing-range map (32 ms/call at 50k ranges) | Validate only at durability boundaries (forced checkpoints, resume, completion) | `test_perf_cadence_20261119.py`: validation calls < chunks/4 while the final boundary still validates |
| Optimization (HIGH) | Adaptive full scan wrote a durable checkpoint (2×fsync + rename + dir-fsync, 4.15 ms) after **every** chunk | Time-throttled non-forced saves (2 s); forced saves on abort/status/completion unchanged | measured: **256 chunk saves → 2** for a 256 MiB scan; resume test still completes |
| Darwin (HIGH) | Rescue imaging declared marginal sectors missing without ever using the shipped consensus engine | Retry pass now attempts `consensus_read` (shifted rereads, majority vote) on a lost sector, bounded by attempts and a sector budget, recorded as `consensus_recovered_bytes` / `consensus_recovered_ranges` provenance — never as verified data | `test_rescue_consensus_20261119.py`: aligned-failure media recovers, budget is bounded, `consensus_attempts=0` restores old behaviour |
| Darwin/Darwin #2, Security #1 | SMART surface was seven raw counters, one USB bridge type, no logs | Full ATA attribute table (bounded 64) with normalised values and thresholds; read-only self-test/error logs; up to four ordered USB bridge device types in a 25 s budget; log reads skipped for failing controllers and NVMe | `test_smart_breadth_20261119.py` (7 tests) |
| Dev (HIGH) | Rescue CLI printed JSON on both `--json` and human paths | Human path prints a compact status line; `--json` unchanged | `test_review_fixes_20261119.py` |
| Dev (MEDIUM) | `scanner.attempt` caught `TypeError` around the progress call, masking a `TypeError` raised **inside** the callback | Callback arity bound once via `inspect.signature`; no try/except around the call | same file |

## Deferred, with reasons

- **Per-drive history / trend** (Darwin #3): needs a persistence format and a
  retention policy; the CLI monitor exists but is not surfaced in Qt.
- **Vendored smartctl authentication** (Security #1): the staged-binary SHA-256
  sidecar is tamper-evidence, not publisher authentication. Adding Authenticode
  verification needs a signed vendor binary to test against.
- **Condition index reframing** (Darwin #4): rename and show the derivation. A
  copy change with product implications; should be decided, not slipped in.
- **File-recovery breadth** (Darwin #5): ext undelete and partition-table
  reconstruction. Substantial new capability.
- **Write benchmark / error-tolerant comparison** (Darwin #6).
- **Full-capacity verification** (Darwin #7): destructive; needs separate gating.
- **Reuse/retire decision artifact** (Darwin #8): the honest e-waste
  differentiator, but it requires deciding what evidence is sufficient.
- **`qtgui.py` extraction into `JobRunner`** (Dev #2): the staged plan is
  recorded; each stage needs fixture-driven GUI tests first. Not a big-bang.
- **QProcess `deleteLater()` leaks, exit-code standardisation, resume
  `refresh_total`** (Dev): real but low severity; grouped for a follow-up.
- **`_validate_state` residual risk**: a cheap per-chunk invariant assert was
  not added; boundary validation plus the resume re-validation cover the
  durability contract.

## Hardware verification (Alienware17R3, 3 external drives)

Read-only triage scans through the app's own CLI, run elevated (Windows blocks
raw physical-drive reads for unelevated processes):

| Drive | Status | Attempted | Read errors | Notes |
|---|---|---|---|---|
| PhysicalDrive2 — SanDisk SDSSDH3 500 GB SSD | completed | 23.5 MiB | 0 | 0.20 s |
| PhysicalDrive3 — Seagate ST1000LM048 1 TB HDD | completed_with_slow_regions | 25.2 MiB | 0 | one 110 ms first read at offset 0 (cold start), 0.69 s |
| PhysicalDrive4 — 3.77 GB flash | completed | 23.4 MiB | 0 | 1.52 s |

Coverage is a **24-sample spot check** (~0.005 % of each large drive), not a
health or capacity certificate. SMART is UNKNOWN on this host (no smartmontools).

Reproduce with:

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\qa_readonly_triage.ps1
python scripts/qa_summarize_results.py %USERPROFILE%\dr_results
```

## Not verified

- No in-place write, capacity test, or repair was performed on the user's disks.
- Windows-native ioctl paths and USB flash statuses were not exercised.
- The dev reviewer reported a full-suite hang in its sandbox; this host ran the
  full suite to completion, so that is attributed to its environment until
  reproduced.
