# Status — 2026-11-01

PRIVATE TEST ONLY — **0.2.6**

## Live Adaptive CLI UI (pass4)

- Elevated dashboard is painting correctly on `windows:PhysicalDrive2` (12 TB USB).
- Root cause of blank PowerShell UI: piping Python stderr through `$ErrorActionPreference=Stop` + using `$args`.
- Launcher: `desktop/scripts/run_elevated_adaptive_refresh.ps1` (real console, no stderr pipe).

## BitLocker

- `inspect-encryption` + fail-closed gates on carve/undelete/ext check-repair.
- Docs: `docs/BITLOCKER_AND_ENCRYPTION.md`
- Safe path: raw image / byte-identical refresh → unlock with recovery key → then file recovery.
