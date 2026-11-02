# Issues — 2026-11-02

## Forge triage
- Applied engineering package **0.3.3b13** (Windows volume lock fail-closed + cooperative scan Stop).
- Closed Repository Detective MEDIUM ruff cluster **#107–#152** (43 issues) via [PR #154](https://git.commsnet.org/commstech/DriveRepair/pulls/154) (`f5a30f4`).
- Applied engineering package **0.3.3b12** (bounded I/O + cooperative STOP + Qt) on `feature/0.3.3b12-bounded-io-qt`.

## Hardware follow-ups (still open / not forge-filed)
- Disposable NTFS/exFAT: open-file must fail lock with zero writes; then Fix with `--auto-lock-volumes`
- Multi-partition / GUID-only / BitLocker / dock disconnect: safe rejection
- ST1000LM048 SMR full elevated verify still blocks public release
- Private lab: confirm cooperative STOP does not leave exclusive volume locks held
- Get-Disk Storage hang after dock reseat: inventory now CIM/WMIC-first; write path still requires Get-Disk identity

## Findings
- Details: `docs/FINDINGS_REMEDIATION_20261102.md`
- Bounded I/O / safe stop: `docs/BOUNDED_IO_AND_SAFE_STOP_0.3.3b12.md`
