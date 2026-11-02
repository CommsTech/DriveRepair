# Architecture notes — 0.3.3b13 desktop

1. **Windows volume lock** — before exclusive raw writes, every enumerated partition must expose a lockable volume GUID/letter; empty access paths and unrecognized partitions fail closed (`repair_blocked_prewrite_access`) without discarding the scan report.
2. **Cooperative STOP** — read-only scan and care honor STOP at completed I/O boundaries; Qt escalates to terminate/force-kill only for stuck read-only children and never labels that as a completed repair.
3. **Inventory vs write gate** — list/select use CIM/WMIC-first inventory (stable fingerprints); physical writes add `assert_windows_external_write_gate` (Get-Disk online/external) without replacing list fingerprints (USB Size disagreement).
4. **Bounded investigation / media profiles / auto-lock** — retained from 0.3.3b8–b12.
