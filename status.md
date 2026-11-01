# Status — 2026-11-01

PRIVATE TEST ONLY — **0.3.0b1** engineering candidate + soft mechanical indicators.

## Applied

- 0.3.0b1 overlay (catalog/TSK/monitor/forensics/triage/GUI/recovery-core) merged with preserved multi-FS + carve work
- Soft indicators on refresh: `--acoustic-watch`, `--shock-guard`, `--smart-deltas` (WATCH/STOP; not platter metrology)
- `detect-filesystems` / `recover-image` CLI wired; SensorSuite attached to refresh progress + pre-write shock gate
- Release notes/artifacts under `docs/releases/0.3.0b1/`
- Identity fingerprint + `--confirm-identity`; Get-Disk discovery; optional Linux RAM journal

## Live hardware notes

- 12 TB Seagate USB: Adaptive disk-journal completed (0.2.7)
- SanDisk 500 GB #1/#2: reads OK; writes failed WinError 1117/121 (dock/drive)
- SanDisk 500 GB #3 (`e8985dc11d53`): write probe OK; Adaptive completed with 0 rewritten
