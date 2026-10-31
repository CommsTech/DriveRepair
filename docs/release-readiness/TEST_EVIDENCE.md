# TEST_EVIDENCE — Gate 0/1

**Rule:** Never invent `PASS`. Unknown or unrun → `NOT_PROVEN` / `SKIPPED` / `BLOCKED`.

**Environment:** Windows workstation · path `c:\Users\commstech\Github\DriveRepair`  
**HEAD (mission start):** `e7396368828bef08d534a1f2442d0e382243cf9e`  
**Branch tip (pushed):** `f5177a7` on `remediation/gate0-safety-2026-10-31`  
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

### T-01 — Library unit tests (initial docs pass — historical)

| Field | Value |
|---|---|
| Date | 2026-10-31 (early Gate 0 WIP) |
| Command | `cargo test --features "std,alloc" --lib` |
| Exit code | **101** |
| Result | **FAIL** (did not compile; tests not executed) |
| Notes | Historical only. Mid-integration UI/mock compile errors later fixed before push. |

### T-01b — Library unit tests (post-fix, pushed tip)

| Field | Value |
|---|---|
| Date | 2026-10-31 |
| Commit | `f5177a7` |
| Command | `cargo test --features "std,alloc" --lib` |
| Exit code | **0** |
| Result | **PASS** — 42 passed; 0 failed; 3 ignored |
| Notes | Includes Gate 0 safety tests (RO write deny, zero write_count on scan, empty SMART → Unknown, Unsupported stubs). Hosted AHCI/NVMe detect tests ignored. Does **not** prove hardware I/O, ISO boot, or ddrescue rescue. |

### T-02 — Toolchain / baseline probes

| Command | Exit | Result | Notes |
|---|---|---|---|
| `git rev-parse HEAD` | 0 | PASS (probe) | `e7396368828bef08d534a1f2442d0e382243cf9e` |
| `rustc --version` / `cargo --version` | 0 | PASS (probe) | 1.96.0-nightly family |
| `Get-FileHash …\DriveRepair-main.zip` | 0 | PASS (probe) | SHA-256 matches baseline `02707c5a…` |
| Top-level `*.iso` presence | 0 | PASS (probe) | `NO_TOP_LEVEL_ISO` |

### T-03 — Clippy / fmt (pre-push on tip `f5177a7`)

| Field | Value |
|---|---|
| Commands | `cargo fmt --check`; `cargo clippy --features "std,alloc" --lib -- -D warnings` |
| Exit code | **0** |
| Result | **PASS** (pre-push hook on push to Gitea) |

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

## Acceptance tests still required before broader PRIVATE_TEST_ONLY hardware use

1. ~~Green `cargo test --features "std,alloc" --lib`~~ — done on tip `f5177a7` (T-01b).
2. Linux VM: ddrescue orchestrated rescue on loop/`dm-*` images with mapfile off-source.
3. QEMU boot of **product** Linux live ISO (not homemade EFI alone).
4. Sacrificial external-device matrix on Win/macOS/Linux (desktop path).

Until ISO + fault-injection + owner-approved hardware matrix: public release remains **NOT_READY**. Desktop scanner remains **PRIVATE_TEST_ONLY**.

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
