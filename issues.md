# Issues — 2026-11-02

## Forge open (addressed this session on `feature/issues-164-172-dock-preflight`)

| # | Title | Status in branch |
|---|---|---|
| 164 | Cooperative stop during adaptive media probing | Fixed + synthetic tests |
| 165 | Align native Windows device fallback bus identity | Fixed + mocked fingerprint tests |
| 166 | Scan completion / coverage clarity in GUIs | Fixed (Tk + Qt messaging) |
| 167 | Conservative quick preflight estimate | Fixed (`format_quick_preflight`) |
| 168 | Rescue journal sync batching | Deferred (safety-sensitive; needs measured throughput + crash injection) |
| 169 | Rescue missing-range sort superlinear | Deferred (same PR family as #168) |
| 170 | Bound carving signature-candidate memory | Fixed (heap merge iterator) |
| 171 | Harden GUI debug log path / privacy | Fixed (temp path; no lab hardcode; POSIX chmod) |
| 172 | Revalidate partition inventory after volume locks | Fixed (signature recheck + docs of remaining race) |

Also: early exclusive-lock preflight in `care-external --auto-lock-volumes` so busy volumes fail closed without a multi-hour quick scan first.

## Hardware follow-ups

- Dual USB dock: SanDisk SDSSDH3 500G + Seagate ST1000LM048 — elevated matrix + GUI still required before macOS testing
- Confirm cooperative STOP releases exclusive volume locks
- ST1000LM048 SMR full elevated verify remains public-release gate

## Closed earlier

- Repository Detective MEDIUM ruff cluster **#107–#152** via PR #154
- Engineering packages 0.3.3b12 / 0.3.3b13 applied on main
