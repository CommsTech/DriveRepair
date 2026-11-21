# DriveRepair release status — v0.3.3b40 (2026-11-21)

**Status: development / guarded testing, not a hardware-qualified public physical-repair release.** The source is an engineering tree; public image-only and guarded physical-repair distributions must be built separately. The latest Python tests do not demonstrate real physical HDD repair, Windows USB flashing, correct native Qt layout, or BIOS/UEFI bootability.

## Available channels

- `python scripts/build_desktop.py --public-beta --no-wheel`: public image-first zipapp; in-place physical writes disabled by embedded distribution policy.
- `python scripts/build_desktop.py --repair-beta --no-wheel`: guarded beta with guided, journaled HDD-targeted writes. Only for sacrificial hardware.
- Source/engineering CLI: includes advanced experimental commands; do not distribute as a qualified public repair product.

## Competitive-gap progress

- **b38:** gap matrix + media-maintenance planner + outcome-first Qt Repair; SSD refresh fail-closed.
- **b39:** latency-prioritized weak-region recovery + optional SMART bookend.
- **b40:** read-only lost-partition scan (`scan-lost-partitions`); no automatic table rewrite.

## Promotion evidence and current gates

The source snapshot is **NOT_PROVEN** for real firmware boot or Windows physical repair.
See `docs/QUALIFICATION_GATES.md` and `docs/COMPETITIVE_GAPS_2026-11-21.md`.

**No guarantee:** SMART health passes and clean sample scans do not certify restored file integrity or future media lifespan.
