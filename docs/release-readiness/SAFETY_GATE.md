# SAFETY_GATE — Gate 0 containment rules

**Status:** Contained for private development only. **Not** a public-release pass.  
**Branch:** `remediation/gate0-safety-2026-10-31` vs HEAD `e739636…`

This document states the Gate 0 rules and where the current tree enforces (or fails to enforce) them. Claims without executed tests are **NOT_PROVEN**.

---

## 1. AccessMode — read-only default

| Rule | Default mode is read-only; writes require explicit opt-in. |
| Enforcement | `AccessMode` enum with `#[default] ReadOnly` — `src/disk/mod.rs:44-52`. `Disk::access_mode()` defaults ReadOnly — `src/disk/mod.rs:206-209`. `RepairConfig.allow_writes` defaults `false` — `src/repair/mod.rs:72-91`. |
| Write gate | `write_sector_with_verify` returns `WriteDenied` unless config + disk are ReadWrite — `src/repair/mod.rs:317-325`. MockDisk rejects writes in ReadOnly — `src/disk/mock.rs:243-249` (authored; suite compile **FAIL** → behavior **NOT_PROVEN** by green run). |
| Gap | UEFI `disk_wrapper` write path checks media RO flag only — `src/boot/uefi/disk_wrapper.rs:116-132` — does not use `AccessMode`. |

---

## 2. Fail-closed `Unsupported`

| Rule | Unimplemented I/O must never return success. |
| Enforcement | ATA read/write/flush → `Err(Unsupported)` — `src/disk/ata.rs:103-128`. Same for SATA/NVMe/USB backends. TRIM/secure erase → `WriteDenied`/`Unsupported` — `src/repair/mod.rs:339-355`. SMART stubs → `Unsupported`/`Unavailable` — `src/smart/ata_smart.rs:28-87`. |
| Gap | UEFI Block I/O `write_blocks` is a real write when media permits. Experimental/unshipped per `src/boot/EXPERIMENTAL.md`. |

---

## 3. SMART — Unknown on empty

| Rule | Empty / unqueried attributes must not be reported Healthy. |
| Enforcement | `SmartParser::interpret_health(&[])` → `Unknown` — `src/smart/mod.rs:115-120`, unit test `196-201`. `AtaSmartExecutor::health_status` maps empty/Unsupported → `Unknown` — `src/smart/ata_smart.rs:65-74`. |
| Gap | Hardware SMART/NVMe logs **NOT_PROVEN** (no device I/O). |

---

## 4. No “Repaired” on read

| Rule | A successful read is not a repair claim. |
| Enforcement | `SectorOutcome::ReadOk` documented as not repaired — `src/repair/mod.rs:18-23`. Scan path maps read success + no expected CRC → `ReadOk` — `src/repair/mod.rs:278-285`. Stats: `repaired` only for `RewriteVerified` — `src/repair/mod.rs:358-400`. |
| Gap | UI still mismatched to old `RepairResult::Recovered`/`Failed` arms at documentation time (`src/ui/mod.rs` compile errors) — display honesty **NOT_PROVEN** until UI compiles. |

---

## 5. Source ≠ destination rules

| Rule | Destination must not resolve to the selected source (path or serial). Unknown identity fails closed. |
| Enforcement | `DeviceIdentity::conflicts_with` — `src/disk/mod.rs:98-105`. `validate_source_destination` — `src/rescue/mod.rs:16-27`. `RescuePlan::new` validates before construction — `39-52`. Unit tests for same path/serial/unknown — `73-105`. |
| Gap | No runtime wiring into a live rescue job against block devices. Boot-media exclusion (**P0-04**) still absent. Overlapping partitions/RAID/ZFS members **not** modeled. |

---

## 6. USB scripts disabled

| Rule | Destructive USB provisioning must hard-fail pending safety gates. |
| Enforcement | Early `exit 2` with explicit error — e.g. `scripts/create_usb.ps1:1-8`, `scripts/deploy_full_usb.ps1:1-8`, plus `make_bootable_usb.ps1`, `setup_usb_only.ps1`, `build_and_install_usb*.ps1`, `quick_build_usb.ps1` (Gate 0 prefix). Original bodies preserved unreachable. |
| Gap | Disable is operator containment. Re-enable requires owner approval after Gate evidence. |

---

## 7. Zero-source-write test plan

### Required properties (Gate 0)

1. Unimplemented backends return `Unsupported` for read/write.
2. Empty SMART → `Unknown`, never `Healthy`.
3. `AccessMode::ReadOnly` rejects writes (`WriteDenied`); write_count stays 0.
4. MockDisk scan with `allow_writes: false` never increments write_count.
5. Sequential scan over large range (e.g. 0..1_000_000) does not allocate O(n) LBA Vec / OOM.
6. `max_attempts == 0` does not panic.

### Authored locations

`src/disk/mock.rs` tests (~193–310); SMART empty test in `src/smart/mod.rs:196-201`; rescue identity tests in `src/rescue/mod.rs:73-117`.

### Execution status (2026-10-31)

| Command | Result |
|---|---|
| `cargo test --features "std,alloc" --lib` | **FAIL** — exit **101** (compile errors). Property proofs **NOT_PROVEN**. |

Do **not** mark this gate PASS until a clean test run is captured in [TEST_EVIDENCE.md](TEST_EVIDENCE.md).

---

## Hard-stop checklist (public release)

A single failure blocks public beta:

- [ ] RO default proven by green tests
- [ ] No false-success destructive stubs on product paths
- [ ] Identity + src≠dst + boot-media exclusion on product paths
- [ ] Off-source durable mapfile with restart proof
- [ ] Zero source writes in rescue modes (instrumented)
- [ ] USB/ISO burn paths owner-approved and evidenced
- [ ] No homemade unsigned bootloader as sole ship vehicle without experimental labeling

**Current:** multiple boxes unchecked → `PUBLIC_RELEASE_BLOCKED`.
