# Status — 2026-11-01

PRIVATE TEST ONLY — **0.2.9b1** + findings remediation + multi-FS recover.

## Applied

- Identity fingerprint + `--confirm-identity` for physical writes
- Get-Disk-preferred Windows discovery; Linux-only RAM journal + power guard
- Chunk sizes up to 64 MiB; lazy large-image rescue jobs
- Repository Detective export validated: DriveRepair open findings repaired; nettech/RD rows out of scope
- Unit suite: **106 tests, OK (skipped=2)**

## Live hardware notes

- 12 TB Seagate USB: Adaptive disk-journal completed (0.2.7)
- SanDisk 500 GB #1/#2: reads OK; writes failed WinError 1117/121 (dock/drive)
- SanDisk 500 GB #3 (`e8985dc11d53`): write probe OK; Adaptive completed with 0 rewritten (no slow probes) — supports hardware/dock fault on prior units, not a software write-path bug
