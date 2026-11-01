# Status — 2026-11-01

PRIVATE TEST ONLY — **0.2.8** readable PowerShell CLI dashboard.

## CLI UX

- In-place ANSI panel for live Adaptive/Full refresh (no scrolling probe wall)
- Compact throttled line mode when redirected
- Human `list` table + scan progress bar; ASCII-only status (no cp1252 mojibake)
- Windows USB discovery falls back to WMIC/CIM when `Get-Disk` hangs after dock reseat
- Internal one-off lab scripts stay local (not shipped in the repo tree)

## Live notes

- 12 TB Seagate USB: Adaptive disk-journal completed (0.2.7)
- Sandisk 500 GB USB: reads OK; writes failed WinError 1117/121 (dock/drive) — not write-certified
