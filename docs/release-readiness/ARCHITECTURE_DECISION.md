# ARCHITECTURE_DECISION — ADR Gate 0/1 product path

**Status:** Accepted for Gate 0/1 planning (not yet implemented as a shippable ISO).  
**Date:** 2026-10-31  
**Context:** Competitive audit + source inventory showed homemade BIOS/UEFI loaders and stubbed raw I/O cannot honestly claim SpinRite-class recovery or public readiness.

---

## Decision

**Ship the recovery product as:**

1. **Linux live ISO** (read-only-by-default operator environment)
2. **Rust orchestrator** (DriveRepair library/CLI) for identity checks, AccessMode policy, plan validation, progress/reporting
3. **Proven host tools** for hardware I/O and imaging:
   - `smartctl` (smartmontools) for ATA/SATA SMART
   - `nvme-cli` for NVMe health/logs
   - **GNU ddrescue** for imaging with durable mapfile (off-source)

**Homemade BIOS/UEFI loaders** under `src/boot/bios` and `src/boot/uefi` are **experimental / unshipped**. See `src/boot/EXPERIMENTAL.md`.

**OpenSuperClone** may be evaluated later as an **optional** advanced cloner. Note: OpenSuperClone / HDDSuperClone lineage is **GPLv2**; combining or distributing with DriveRepair requires license review before bundling. Optional = not in Gate 0/1 critical path.

---

## Consequences

| Positive | Negative / work remaining |
|---|---|
| Uses battle-tested imaging (ddrescue mapfile) instead of inventing journal format first | Need reproducible ISO build, SBOM, and QEMU boot proof (**NOT_PROVEN** today) |
| SMART/NVMe via maintained tools reduces false “Healthy” stubs | Orchestrator must still fail-closed on missing tools / unknown identity |
| Separates diagnose/rescue from in-place remediation | Homemade boot code debt remains; must stay labeled experimental |
| Aligns with audit Gate B synthetic tests (`dm-*` on Linux) | Windows workstation cannot run dm-dust/flakey — those tests **BLOCKED** here |

---

## Alternatives considered (rejected for Gate 0/1 ship vehicle)

| Alternative | Why rejected |
|---|---|
| Homemade UEFI/BIOS as primary product | Incomplete I/O, real `write_blocks` path, no ISO, identity/boot-exclusion gaps; EXPERIMENTAL |
| Pure Rust raw ATA/AHCI/NVMe in freestanding env first | Stubs dominate; high risk of false success; privileged I/O unsafe on hosted test hosts |
| Claim parity with SpinRite DynaStat-class recovery via port I/O alone | Proprietary internals not available; audit forbids marketing clone claims without measured evidence |
| Windows-hosted “repair” against physical disks | Wrong trust boundary; USB scripts deliberately disabled (`exit 2`) |
| Bundle OpenSuperClone as default | License (GPLv2) + scope; keep optional pending legal/product review |

---

## Current tree alignment

| Element | State |
|---|---|
| Rescue scaffold | `src/rescue/mod.rs` — identity validation + ddrescue argv builder only |
| AccessMode / fail-closed | Library Gate 0 remediation in progress on branch |
| Live ISO | **Absent** (no top-level `.iso`) |
| Homemade boot | Present; marked experimental |
| USB burn scripts | Disabled pending safety gates |

---

## Follow-on ADRs (not decided here)

- Exact live-ISO base (Debian/Ubuntu/Fedora rescue) and Secure Boot story
- Whether OpenSuperClone is vendored, documented-as-external, or omitted
- Signing/reproducible-build pipeline for Gate F packaging
