# DriveRepair vs SpinRite and competing recovery tools

**Comparison date:** 2026-11-21  
**DriveRepair baseline:** `0.3.3b39` (extends `0.3.3b38` source)  
**SpinRite publicly confirmed:** 6.1 production; 6.2 under development (UEFI boot testing reported 2026-11-17; not a published production release).

This document is a **gap list and roadmap**, not a claim that every SpinRite/Sentinel write mode should be enabled. Physical failures that need replacement or a recovery lab remain out of scope for software alone.

## 1. SpinRite 6.1 capabilities vs DriveRepair

| SpinRite capability | DriveRepair today | Gap | Priority |
|---|---|---|---|
| Native high-speed IDE/SATA/AHCI drivers | OS-level device interfaces (Win32/POSIX) | **Major** — no proprietary bus drivers | P6 / hardware-adjacent |
| Intensive DynaStat-class sector recovery | Latency-prioritized weak-region pass + optional SMART bookend | **Partial** — improved in b39 | P3 |
| Full-drive read/rewrite refresh on SSDs | SSD physical refresh not offered (fail-closed) | **Major** — needs qualified opt-in design | P2 |
| Five operating levels (inspect → intensive rewrite) | Separate scan / rescue / restricted HDD maintenance | **Partial** — unified planner added in b38 | P2 |
| Temperature-aware cooling + resume | Power/temperature safeguards exist | **Partial** | P3 |
| Continuous SMART during work | Health checks + history; less integrated | **Partial** | P3 |
| Before/after benchmarks with maintenance | Benchmark code exists; weakly integrated | **Partial** — planner exposes assess hooks | P2 |
| Mature direct-boot BIOS experience | Debian live ISO recipe; hardware boot NOT_PROVEN | **Major** | **P1** |

SpinRite limitations (for context): BIOS-era firmware expectations; USB/NVMe often via BIOS services; not a file-level/RAID reconstruction suite.

### SpinRite level mapping (documentation analogue)

| Level | Documented SpinRite behavior | DriveRepair analogue (b38 planner) | Write status |
|---|---|---|---|
| 1 | Scan without repair | `inspect_readonly` | Never writes |
| 2 | Attempt recovery of troubled sectors | `weak_region_reread` / rescue multipass | Read-only / image |
| 3 | Read and rewrite media | `hdd_region_refresh` (HDD only, gated) | Opt-in, journaled |
| 4 | Extra verification read | `verify_after_maintenance` | Follows prior write |
| 5 | Inverted write/read then restore | `intensive_pattern_cycle` | **Not enabled** — research only |

## 2. Other competitors

| Application | What it does that DriveRepair does not yet do well | Priority |
|---|---|---|
| Hard Disk Sentinel | Multi-mode surface tests, SSD/flash refresh, destructive reinit, rich SMART history | P2–P3 |
| Victoria HDD/SSD | Low-level interrogation, remap/erase, broad ATA/NVMe/SAS | P3 / P6 |
| HDD Regenerator | Aggressive “regeneration” claims — verify independently | Research only |
| OpenSuperClone | Direct AHCI/IDE, power-cycle integration, virtual-disk extraction | P4 / P6 |
| R-Studio | Filesystem reconstruction, virtual RAID, network recovery | P4 |
| UFS Explorer | RAID, encrypted volumes, VMware/forensic imaging | P4 / P6 |
| DMDE | Partition tables, NTFS analysis, RAID, hex | P4 |
| TestDisk / PhotoRec | Lost partitions, boot-sector repair, signature carving (bundled in live ISO, not fully integrated UX) | P4 |
| Disk Drill | Polished guided recovery, preview, Recovery Vault | P5 |
| Stellar Data Recovery | Broader deleted-file/preview/encrypted workflows | P4–P5 |
| DeepSpar (lab class) | Hardware reset/power timing; region↔file linkage | P6 — may need hardware |

## 3. Largest feature gaps (A–E)

| ID | Gap | Closing order |
|---|---|---|
| A | Multi-media maintenance / qualified refresh (HDD vs SSD/NVMe/flash) | **P2** (planner in b38; SSD writes remain disabled) |
| B | Hardware diagnostics integration + larger model catalog | P2–P3 |
| C | Filesystem/partition/RAID depth | P4 |
| D | Unstable-drive control (resets, file-prioritized imaging) | P4 / P6 |
| E | Consumer outcome-first UX + real Windows/USB proof | **P1** + **P5** |

## 4. Recommended development order (active)

1. **P1 — Make existing Windows + recovery-USB engines reliable**  
   Dock access, identity, SMART, volume mapping, boot-media qualification on disposable hardware.
2. **P2 — Unified media-aware maintenance engine**  
   One interface for HDD / SSD / NVMe / flash: filesystem repair, self-tests, read verification, *qualified* refresh where feasible; risky writes opt-in only.
3. **P3 — Stronger weak-region recovery**  
   Adaptive rereads, latency maps, deadlines, SMART-during-work; fixture benchmarks vs SpinRite/OpenSuperClone concepts.
4. **P4 — Restore files better**  
   Lost partitions, deeper NTFS/exFAT, signatures, fragmented media, file-prioritized imaging.
5. **P5 — Outcome-first UI**  
   Detect problem → choose backend → show usable results without requiring SMART literacy.
6. **P6 — Technician / lab capabilities**  
   Batch, RAID, crypto volumes, remote ops, optional hardware integrations.

## 5. Distinction that matters

Making every **media type serviceable** is not the same as claiming every **physical failure** can be fixed. Exhausted NAND, dead controllers, and lost encryption keys require replacement or a lab — software must say so clearly.

## 6. Closing status (this tree)

| Item | Status in this release |
|---|---|
| Published gap matrix | **Done** (this file) |
| Unified maintenance *planner* (no silent SSD writes) | **Done** (`media_maintenance.py`) |
| Outcome-first Repair guidance wiring | **Done** (Qt ready strip, profile, eligibility dialog) |
| Manufacturer catalog coverage | **Improved** (10 sourced entries; still incomplete) |
| P3 weak-region latency prioritization + SMART bookend | **Done** (`weak_region_recovery.py`; still no native AHCI) |
| P1 hardware qualification on real dock/USB/ISO | **NOT_PROVEN** — operator evidence required |
| SSD qualified refresh engine | **Not enabled** — planned op only |
| Native AHCI/IDE drivers / DeepSpar-class control | **Out of band** |
