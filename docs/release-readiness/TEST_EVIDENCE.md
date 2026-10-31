# TEST_EVIDENCE — Gate 0/1

**Rule:** Never invent `PASS`. Unknown or unrun → `NOT_PROVEN` / `SKIPPED` / `BLOCKED`.

**Environment:** Windows workstation · path `c:\Users\commstech\Github\DriveRepair`  
**HEAD (mission start / still tip):** `e7396368828bef08d534a1f2442d0e382243cf9e`  
**Branch:** `remediation/gate0-safety-2026-10-31` (dirty Gate 0 working tree)  
**Toolchain:** `rustc 1.96.0-nightly (23903d01c 2026-03-26)` · `cargo 1.96.0-nightly (e84cb639e 2026-03-21)`

---

## Template (reuse for future runs)

```
Date (ISO):
Operator:
Commit:
Command:
Working directory:
Exit code:
Result: PASS | FAIL | SKIPPED | BLOCKED | NOT_PROVEN
Notes / key output (verbatim excerpt):
```

---

## Executed this session

### T-01 — Library unit tests

| Field | Value |
|---|---|
| Date | 2026-10-31 |
| Command | `cargo test --features "std,alloc" --lib` |
| Exit code | **101** |
| Result | **FAIL** (did not compile; tests not executed) |
| Notes | Compiler errors included: `src/ui/mod.rs` still matches removed `RepairResult::Recovered` / `Failed`; `SmartHealthStatus::UnableToQuery` unmatched; `scan_and_repair` callback typed as `Fn` but mock test mutates capture (`FnMut` needed) in `src/disk/mock.rs`. |

**Do not claim safety property PASS.** Zero-source-write tests are authored but **NOT_PROVEN**.

### T-02 — Toolchain / baseline probes

| Command | Exit | Result | Notes |
|---|---|---|---|
| `git rev-parse HEAD` | 0 | PASS (probe) | `e7396368828bef08d534a1f2442d0e382243cf9e` |
| `rustc --version` / `cargo --version` | 0 | PASS (probe) | 1.96.0-nightly family |
| `Get-FileHash …\DriveRepair-main.zip` | 0 | PASS (probe) | SHA-256 matches baseline `02707c5a…` |
| Top-level `*.iso` presence | 0 | PASS (probe) | `NO_TOP_LEVEL_ISO` |

### T-03 — `cargo check` (library)

| Field | Value |
|---|---|
| Command | *(not re-run as a dedicated check after final UI edits in this docs pass)* |
| Result | **NOT_PROVEN** this documentation session |

Historical inventory (earlier same-day audit) reported `cargo check --features "std,alloc"` exit 0 on pre-Gate-0 tree — that result must not be reused as proof for the current dirty Gate 0 tree.

---

## Planned / environment-blocked

| ID | Scenario | Result | Reason |
|---|---|---|---|
| T-10 | `dm-dust` localized EIO rescue | **BLOCKED** | Requires Linux device-mapper; not available as native Windows workstation lab here |
| T-11 | `dm-flakey` intermittent EIO | **BLOCKED** | Same |
| T-12 | `dm-delay` slow-read behavior | **BLOCKED** | Same |
| T-13 | `dm-flakey` corrupt_bio_byte silent corruption | **BLOCKED** | Same |
| T-14 | Mid-run crash + mapfile resume | **SKIPPED** | No durable mapfile implementation / no Linux harness run |
| T-15 | Device identity swap mid-run | **SKIPPED** | Not executed |
| T-16 | QEMU UEFI boot of product ISO | **BLOCKED** / **SKIPPED** | No product ISO in tree; QEMU ISO boot not run this session |
| T-17 | QEMU BIOS boot | **SKIPPED** | Same |
| T-18 | Physical USB burn smoke | **SKIPPED** | USB scripts disabled (`exit 2`); owner approval required; not run |
| T-19 | Real-disk sacrificial lab | **SKIPPED** | Out of Gate 0 scope; forbidden without owner approval |
| T-20 | Head-to-head vs SpinRite 6.1 | **SKIPPED** | No controlled lab this session → feeds `BETTER_THAN_SPINRITE = NOT_PROVEN` |

---

## Acceptance tests still required before PRIVATE_TEST_ONLY

1. Green `cargo test --features "std,alloc" --lib` with captured summary (zero write_count proofs).
2. Linux VM: ddrescue orchestrated rescue on loop/`dm-*` images with mapfile off-source.
3. QEMU boot of **product** Linux live ISO (not homemade EFI alone).
4. Explicit refusal tests: same-serial src/dst; unknown identity; RO mode write deny.

Until then: **NOT_READY**.

## Workstation re-run 2026-10-31 (Windows)

| Command | Exit | Result |
|---|---|---|
| `py -3 -m unittest discover -s tests -v` (cwd desktop, PYTHONWARNINGS=error) | 0 | 19 passed |
| `cargo test --features "std,alloc" --lib` | 0 | 42 passed, 3 ignored |
| `py -3 -m driverepair_desktop list --json` | 0 | `[]` (no qualifying external disks) |
| Physical USB full scan | SKIPPED | No owner-approved sacrificial device this session |
| QEMU/OVMF ISO boot | SKIPPED / BLOCKED | No product ISO artifact |
| dm-dust/flakey/delay | SKIPPED | Requires Linux fault-injection environment |

HEAD base: e7396368828bef08d534a1f2442d0e382243cf9e on branch remediation/gate0-safety-2026-10-31
