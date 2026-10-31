# SOURCE_AUDIT_RECONCILED — Gate 0/1

**Compared against:** ZIP `DriveRepair-main.zip` SHA-256 `02707c5a34d9b4123b63b292b42166c0d7def114bc11e13a04a2ddb511864c99`  
**Mission-start HEAD:** `e7396368828bef08d534a1f2442d0e382243cf9e`  
**Current branch:** `remediation/gate0-safety-2026-10-31` (uncommitted Gate 0 remediation present)  
**ID source:** Audit P0 hard-stops in repo `issues.md` + competitive inventory (2026-10-31 live-tree audit). P1/P2 IDs continue that backlog.

Finding IDs are **not** invented severity scores; they track the Gate 0 hard-stop backlog.

---

## P0 findings

### P0-01 — Fail-closed stubs (no false-success `Ok(())` on unimplemented I/O / TRIM / erase)

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | ATA/SATA/NVMe/USB `write_sectors` and repair `trim_sectors` / `secure_erase` returned `Ok(())` while unimplemented (inventory). |
| Current status | **PARTIALLY_FIXED** (+ **CHANGED** vs ZIP) |
| Evidence | `src/disk/ata.rs:103-128` → `Err(DiskError::Unsupported)` for read/write/flush; same pattern `src/disk/sata.rs`, `nvme.rs`, `usb.rs`. `src/repair/mod.rs:339-355` TRIM/erase → `WriteDenied` and/or `Unsupported`. |
| Residual | Real UEFI Block I/O write path remains: `src/boot/uefi/disk_wrapper.rs:116-132` calls `write_blocks` when media is not RO. Homemade UEFI path is experimental/unshipped (`src/boot/EXPERIMENTAL.md`). |
| Mission action | Gate 0 converted stubs to fail-closed `Unsupported`. |

### P0-02 — Read-only default + explicit destructive opt-in

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | No `AccessMode`; write APIs unrestricted by policy. |
| Current status | **PARTIALLY_FIXED** |
| Evidence | `AccessMode::ReadOnly` is `#[default]` at `src/disk/mod.rs:44-52`. Trait default `access_mode()` → ReadOnly at `src/disk/mod.rs:206-209`. `RepairConfig.allow_writes: false` default at `src/repair/mod.rs:72-91`, `450-454`. `write_sector_with_verify` requires ReadWrite at `src/repair/mod.rs:317-325`. |
| Residual | UEFI wrapper write path does not consult `AccessMode` (only `media.is_read_only()`). Product path not yet the Linux ISO orchestrator. |
| Mission action | Added AccessMode + allow_writes defaults. |

### P0-03 — Device identity + source ≠ destination validation

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | No clone/src–dst validation; identity fields often empty placeholders. |
| Current status | **PARTIALLY_FIXED** |
| Evidence | `DeviceIdentity` + `conflicts_with` at `src/disk/mod.rs:61-106`. Rescue validation at `src/rescue/mod.rs:16-27`, plan construction `39-52`, unit tests `73-117`. Re-exported via `src/lib.rs:28-29`, `34`. |
| Residual | No end-to-end imaging execution; UEFI model/serial still weak/placeholder historically; unknown identities reject plans but production enumeration wiring is incomplete. |
| Mission action | Added `src/rescue/mod.rs` command-builder + identity rejection tests (no real-disk exec). |

### P0-04 — Boot-media exclusion

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | Absent / index-0 heuristic TODO (inventory). |
| Current status | **VALIDATED_AT_HEAD** (gap remains) |
| Evidence | No LoadedImage / boot-handle exclusion found under `src/boot/**/*.rs` (grep). UEFI repair still selects by user index then opens Block I/O handle: `src/boot/uefi/repair_integration.rs:113-134`. Menus no longer auto-pick disk 0 (`menu_integration.rs` returns `Ok(None)`), which reduces accidental selection but is **not** boot-media exclusion. |
| Mission action | Menu auto-select removed; true boot-device exclusion **not** implemented. |

### P0-05 — Durable recovery journal / mapfile (off-source)

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | Absent. |
| Current status | **PARTIALLY_FIXED** (scaffold only) |
| Evidence | `RescuePlan.mapfile_path` + `build_ddrescue_command` at `src/rescue/mod.rs:29-70`. No on-disk journal writer, checksummed atomic updates, or crash-resume implementation in-tree. |
| Residual | Durable mapfile I/O **NOT_PROVEN** / effectively **ABSENT** beyond argv scaffolding. |
| Mission action | Scaffold only; no real ddrescue execution against disks. |

### P0-06 — Tests proving zero source writes in read-only modes

| Field | Value |
|---|---|
| ZIP / pre-Gate-0 | No safety property tests; Windows `cargo test` crashed on privileged port I/O (inventory). |
| Current status | **PARTIALLY_FIXED** — tests authored and green on tip `f5177a7`; proves library RO/zero-write invariants on mocks only |
| Evidence | Authored: `src/disk/mock.rs` safety tests. Hosted port I/O stubs: `src/platform/bios.rs`. |
| Executed | Early WIP: exit 101 (historical). Tip `f5177a7`: `cargo test --features "std,alloc" --lib` → **exit 0** (42 passed, 3 ignored). See [TEST_EVIDENCE.md](TEST_EVIDENCE.md) T-01b. |
| Mission action | MockDisk + safety tests landed; real-device zero-write still **NOT_PROVEN**. |

---

## P1 findings

### P1-01 — Imaging / rescue orchestration incomplete

| Current status | **PARTIALLY_FIXED** |
| Evidence | `src/rescue/mod.rs` builds `ddrescue` argv only; comment at lines 1–2 and 54–55 forbids real-disk execution. No Linux live ISO artifact in repo. |
| Residual | Product rescue path **NOT_PROVEN**. |

### P1-02 — SMART false Healthy on empty / stub Ok success

| Current status | **CHANGED** / **PARTIALLY_FIXED** |
| Evidence | Empty attributes → `Unknown` at `src/smart/mod.rs:115-120`, test `196-201`. ATA stubs return `Unsupported`/`Unavailable` at `src/smart/ata_smart.rs:28-87`; health maps Unsupported → Unknown at `65-74`. |
| Residual | No real SMART/NVMe log I/O. Hardware health **NOT_PROVEN**. |

### P1-03 — Privileged port I/O crashing hosted `cargo test`

| Current status | **CHANGED** / **PARTIALLY_FIXED** |
| Evidence | `is_hosted_os()` gates `inb`/`outb`/`outdw` etc. at `src/platform/bios.rs:16-18`, `26-29`, `176+`. |
| Residual | Full suite still fails to compile for unrelated UI/API mismatches — crash fix **NOT_PROVEN** by green test run. |

### P1-04 — Confirmation UX / auto-select disk 0

| Current status | **CHANGED** / **PARTIALLY_FIXED** |
| Evidence | BIOS `src/boot/bios/menu_integration.rs:86-87` → `Ok(None)`. UEFI `src/boot/uefi/menu_integration.rs:74-75` → `Ok(None)`. |
| Residual | Homemade boot UI remains experimental; not a shippable product path. |

---

## P2 findings

### P2-01 — No shippable ISO; homemade BIOS/UEFI packaging confusion

| Current status | **VALIDATED_AT_HEAD** (no ISO) + **CHANGED** (explicit experimental label) |
| Evidence | No top-level `.iso`. `src/boot/EXPERIMENTAL.md` marks homemade loaders unshipped; product path = Linux live ISO. |
| UEFI Cargo.toml vs ZIP | ZIP and current both use `path = "standalone_minimal.rs"` (`src/boot/uefi/Cargo.toml:15`). Baseline note that tree used `main.rs` is **NOT confirmed** on this read — record **SAME as ZIP**, not CHANGED. Full `main.rs` exists beside standalone crate config. |

### P2-02 — Destructive USB provisioning / CI toolchain hygiene

| Current status | **CHANGED** / **PARTIALLY_FIXED** |
| Evidence | USB scripts hard-fail: `scripts/create_usb.ps1:1-8`, `deploy_full_usb.ps1:1-8`, and siblings → `exit 2`. CI uses `dtolnay/rust-toolchain@stable` with Gate 0 ISO note: `.gitea/workflows/ci.yml:7-9`, `17-18`. |
| Residual | Script disable is policy containment, not product readiness. CI ISO build still **NOT_PROVEN**. Action tags not SHA-pinned. |

---

## Mission remediation summary

Gate 0 on branch `remediation/gate0-safety-2026-10-31` (working tree, not merged to `main` at doc time) addresses fail-closed stubs, AccessMode, honest SectorOutcome/SMART Unknown, hosted I/O stubs, menu non-auto-select, USB script disable, rescue scaffold, EXPERIMENTAL boot note, and CI toolchain swap.

**Does not clear PUBLIC_RELEASE_BLOCKED:** boot-media exclusion missing, durable mapfile absent, homemade UEFI writes still possible, no product ISO, no SpinRite head-to-head, no sacrificial hardware matrix. Library `cargo test` is green on tip `f5177a7` but is not a release proof.
