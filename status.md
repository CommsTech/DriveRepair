**0.3.3b13 ENGINEERING CANDIDATE: PRIVATE TESTS ONLY.** Windows volume-lock fail-closed + cooperative scan Stop. Not a public physical-repair release. See `docs/WINDOWS_VOLUME_ACCESS_AND_STOP_0.3.3b13.md`.

# Status — 2026-11-02

PRIVATE TEST — **0.3.3b13** partition-lock / scan-cancellation audit on disposable SanDisk 500GB USB SSD.

## Product

- Version `0.3.3b13`: every enumerated partition needs a lockable Windows volume handle; RAW/unrecognized partitions block repair with `repair_blocked_prewrite_access` while preserving scan findings
- Cooperative STOP for read-only `scan` / Qt escalation messaging
- Prior: CIM/WMIC inventory + inventory-stable select fingerprints; Get-Disk write gate; bounded I/O / STOP (b12)

## Lab

- Patient: SanDisk SDSSDH3 500G USB (sacrificial)
- Journals: RAM-only (`--journal-backend memory`) for applicable write tests — no durable journal images on disk
- Public release: **Blocked** pending Seagate ST1000LM048 elevated verify

Artifacts: `docs/releases/0.3.3b13/`
