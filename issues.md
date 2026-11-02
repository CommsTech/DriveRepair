# Issues — 2026-11-01

## Open forge issues
- ~~#97 unused `rescue_reader` import~~ — fixed on remediation branch

## Findings export triage (`findings-20261102T013909Z.json`)
- DriveRepair had 47 open+unsuppressed findings in a mixed 3-repo export
- Actionable lint fixed; stale #80/#81/#92 confirmed resolved or false-positive
- Details: `docs/FINDINGS_REMEDIATION_20261102.md`

## Still blocked for public release
- Seagate ST1000LM048 full elevated surface verify (error-aware Direct Repair / refresh-external)
- Physical power-loss / USB disconnect / real read-error hardware gates per 0.3.3b4–b5 reports
- Destructive reinitialization of unreadable sectors remains **not implemented**
