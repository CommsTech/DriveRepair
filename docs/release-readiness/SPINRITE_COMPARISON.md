# SPINRITE_COMPARISON — evidence only

**BETTER_THAN_SPINRITE = NOT_PROVEN**

SpinRite 6.1 claims below are **vendor claims** (https://www.grc.com/sr/faq.htm, https://www.grc.com/sr/61for60.htm), not independent lab measurements from this project. DriveRepair cells cite tree evidence or `NOT_PROVEN` / `ABSENT`.

---

## Capability table

| Topic | SpinRite 6.1 (vendor claim) | DriveRepair (this tree) | Evidence grade |
|---|---|---|---|
| Boot environment | BIOS/DOS bootable tool | Homemade BIOS/UEFI **experimental/unshipped**; product path = Linux live ISO (**no ISO in repo**) | DriveRepair boot product **ABSENT** / **NOT_PROVEN** |
| L1-style read-only scan | Yes (Level 1) | Library scan path is read-oriented with `allow_writes: false` default; full product UX **NOT_PROVEN** | Partial code; tests compile **FAIL** |
| In-place rewrite / refresh (L3–L5) | Vendor levels include rewrite/verify patterns | Opt-in `allow_writes` + rewrite APIs gated; TRIM/erase fail-closed; no evidenced L3–L5 equivalent | **NOT_PROVEN** vs SpinRite |
| Proprietary DynaStat-class recovery | Vendor claim | **Not implemented**; must not be claimed | **ABSENT** |
| USB / NVMe support | BIOS-dependent per vendor docs | Stubs `Unsupported` for ATA/SATA/NVMe/USB lib backends; UEFI Block I/O exists experimental | **NOT_PROVEN** on hardware |
| SMART health | Vendor feature set | Parser + fail-closed stubs; empty → `Unknown` | Logic partial; HW **NOT_PROVEN** |
| Imaging + durable mapfile | Not SpinRite’s primary model (in-place focus) | `RescuePlan` argv scaffold for GNU ddrescue only | Scaffold; execution **NOT_PROVEN** |
| Source-write safety in rescue | N/A (different model) | Policy + mock tests authored; suite not green | **NOT_PROVEN** |
| Controlled head-to-head metrics (verified bytes, source writes, time) | — | **Not run** | **NOT_PROVEN** |

---

## Workload classes (do not conflate)

| Class | Fair comparator | DriveRepair status |
|---|---|---|
| Safe imaging / rescue | GNU ddrescue, OpenSuperClone | Scaffold only → **NOT_PROVEN** |
| In-place media refresh | SpinRite L3–L5 (vendor) | Gated/unimplemented → **NOT_PROVEN** |
| Read-only surface characterization | SpinRite L1; ddrescue dry patterns | Library intent present → **NOT_PROVEN** end-to-end |

---

## Verdict line

| Claim | Status |
|---|---|
| DriveRepair is better than SpinRite 6.1 (any workload) | **NOT_PROVEN** |
| DriveRepair matches SpinRite L1–L5 | **NOT_PROVEN** / mostly **ABSENT** |
| DriveRepair is safer by default than in-place rewrite tools | **Policy intent present**; product proof **NOT_PROVEN** |

No marketing language should assert superiority until Gate E lab evidence exists ([TEST_EVIDENCE.md](TEST_EVIDENCE.md) T-20).
