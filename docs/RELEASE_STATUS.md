# DriveRepair release status — v0.3.3b39 (2026-11-21)

**Status: development / guarded testing, not a hardware-qualified public physical-repair release.** The source is an engineering tree; public image-only and guarded physical-repair distributions must be built separately. The latest Python tests do not demonstrate real physical HDD repair, Windows USB flashing, correct native Qt layout, or BIOS/UEFI bootability.

## Available channels

- `python scripts/build_desktop.py --public-beta --no-wheel`: public image-first zipapp; in-place physical writes disabled by embedded distribution policy.
- `python scripts/build_desktop.py --repair-beta --no-wheel`: guarded beta with guided, journaled HDD-targeted writes. Only for sacrificial hardware. Requires independent evidence of rotational HDD, SMART health, stable identity/serial, explicit consent, exclusive OS access, separate journal and postverification.
- Source/engineering CLI: includes advanced experimental commands; do not distribute as a qualified public repair product.

## Recent competitive-gap progress

- **b38:** gap matrix + unified media-maintenance planner + outcome-first Qt Repair guidance; SSD refresh fail-closed.
- **b39:** latency-prioritized weak-region recovery with media-tuned budgets and optional SMART bookend (`weak_region_recovery.py`). Still OS-level I/O — not native AHCI/IDE.

## Engineering and test evidence

- Gap matrix: `docs/COMPETITIVE_GAPS_2026-11-21.md`.
- README and boot-media usability updates: `docs/B18_USB_REPAIR_AND_README_QA.md`.
- Existing guarded preflight and model classification: `docs/USB_REPAIR_PREFLIGHT_B17.md`.
- Windows raw-I/O constraints and stop behavior: `docs/WINDOWS_VOLUME_ACCESS_AND_STOP_0.3.3b13.md`.

## Promotion evidence and current gates

The source snapshot is **NOT_PROVEN** for real firmware boot or Windows physical repair.
`python scripts/check_release_hygiene.py` checks active docs/commands, and
`python scripts/check_release_readiness.py --help` describes the independent
artifact-specific promotion gate. See `docs/QUALIFICATION_GATES.md`.

## Remaining release gates

- Native Windows 10/11 PySide6 clickthrough and usability testing.
- Native Windows physical-access/locking/SAT bridge tests, USB disconnect/power interruption, failing HDD tests with ground truth.
- Bootable ISO reproducibility, BIOS and UEFI boot tests, supported storage controller matrix.
- Trusted original-data-reference checks, recovery journal replay tests, actual postwrite retention tests and SMART trend comparisons.

**No guarantee:** SMART health passes, clean sample scans, successful sector readbacks and a high diagnostic score do not certify restored file integrity or future media lifespan. SSD/NVMe/flash never enter generic HDD rewrite repair.
