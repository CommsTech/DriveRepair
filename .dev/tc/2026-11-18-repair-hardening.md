# Repair hardening — test-first record

**Date:** 2026-11-18
**Scope:** scanner abort reporting and media-refresh journal resume validation.

## Behaviours and tests

1. **Aborted triage scan preserves evidence.** With compare_suspects=True, an error-limit abort returns its normal result dictionary with status=aborted_error_limit and extra_suspect_reads=0.
   - Test: ScannerTests.test_aborted_triage_error_limit_returns_evidence
2. **Device/access abort preserves evidence.** With compare_suspects=True, a device/access abort returns its normal result dictionary with status=aborted_device_or_access_error and extra_suspect_reads=0.
   - Test: ScannerTests.test_aborted_triage_device_error_returns_evidence
3. **Malformed interrupted repair journals fail closed before any write.** A resume transaction with an out-of-bounds or unaligned region is rejected before the media writer is called.
   - Test: RollingJournalTests.test_resume_rejects_malformed_transaction_before_write

### Happy / edge / error / integration coverage

- Happy: existing clean triage comparison and targeted/full refresh tests remain green.
- Edge: abort occurs before optional suspect follow-up reads; evidence counters remain defined.
- Error: malformed transaction metadata is rejected without a media write.
- Integration: the existing desktop repair/recovery suite and craft gate run after the fix.

## Mock matrix

| Test seam | Mock/fake | Why |
|---|---|---|
| Scanner reads | Existing FakeReader with deterministic OSError offsets | Exercises the real scan_reader control flow without hardware. |
| Repair resume | Existing in-memory MemoryMedia plus a real temporary journal and _state_save | Proves the real journal loader/gate and records whether write_at was called. |

No production code has been changed for this record yet. Pre-fix output is recorded below after the failing tests run.

## Pre-fix failure output

The scanner tests raised `UnboundLocalError: cannot access local variable 'extra_attempts' where it is not associated with a value` at scanner.py:418 for both abort statuses. The journal test failed with `AssertionError: ValueError not raised`; the pre-fix resume path accepted the malformed transaction instead of rejecting it.

## Post-fix output

The three regression tests pass after the fix: `Ran 3 tests in 0.462s` / `OK`. The complete desktop suite passes: `Ran 341 tests in 160.659s` / `OK (skipped=11)`.

## Coverage delta

Coverage delta: scanner.py now initializes the abort-safe extra-read counter and has two abort regression tests. media_refresh.py now validates resumed transaction state, digest shape, alignment, bounds, and mode cursor/queue correspondence before recovery; the malformed-journal test proves no write is attempted.

## Release artifact

- Built with `python3 scripts/build_desktop.py --public-beta --no-wheel` from this tree: `BUILD_RC=0`.
- `dist/DriveRepair-0.3.3b13-public-beta.pyz` sha256 `969cf03fb0e90ecb539a7c1bffacb9787a6368d86c90cb05027be3d80d15d6e1`.
- `python3 scripts/check_public_beta.py dist/DriveRepair-0.3.3b13-public-beta.pyz`: `PASS: 6 in-place patient write commands denied; synthetic scan/rescue/status/hash verified`, `CHECK_RC=0`.
- Craft gate: `procode.py gate --staged` → PASS.
