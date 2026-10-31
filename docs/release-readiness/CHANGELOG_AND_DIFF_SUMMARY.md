# CHANGELOG_AND_DIFF_SUMMARY — Gate 0 remediation

**Base commit (mission start / branch tip before merge):** `e7396368828bef08d534a1f2442d0e382243cf9e`  
**Branch:** `remediation/gate0-safety-2026-10-31`  
**Note:** At documentation time, Gate 0 changes are largely **uncommitted** on the branch (working tree dirty). No merge to `main`. No push assumed.

---

## Scope (why)

Contain patient-disk risk before any public or USB-facing release: fail closed, read-only defaults, honest SMART/outcomes, disable destructive USB scripts, stub hosted port I/O so tests can eventually run, scaffold Linux/ddrescue product path, label homemade boot experimental.

---

## Major change areas

| Area | Intent | Representative paths |
|---|---|---|
| Disk API | `AccessMode`, `DeviceIdentity`, new `DiskError`s, `Unknown` interface, checked `size_bytes`, `MockDisk` | `src/disk/mod.rs`, `src/disk/mock.rs` |
| Backends | Unimplemented I/O → `Unsupported` (never `Ok(())`) | `src/disk/ata.rs`, `sata.rs`, `nvme.rs`, `usb.rs` |
| Repair | `SectorOutcome` honesty; `allow_writes` default false; iterator sequential scan; TRIM/erase fail-closed | `src/repair/mod.rs`, `src/repair/recovery.rs` |
| SMART | Empty → `Unknown`; stubs Unavailable/Unsupported | `src/smart/mod.rs`, `src/smart/ata_smart.rs` |
| Platform | Hosted OS: no real `in`/`out` asm | `src/platform/bios.rs` |
| Rescue scaffold | src≠dst + ddrescue argv builder | `src/rescue/mod.rs`, `src/lib.rs` |
| Menus | No auto-select disk 0 | `src/boot/*/menu_integration.rs` |
| Boot policy doc | Homemade loaders unshipped | `src/boot/EXPERIMENTAL.md` |
| USB scripts | Hard fail `exit 2` | `scripts/create_usb.ps1` and siblings |
| CI | Replace `actions-rs/toolchain@v1` with `dtolnay/rust-toolchain@stable`; ISO NOT_PROVEN note | `.gitea/workflows/ci.yml` |
| UI | Updated for `SectorOutcome` / `UnableToQuery` | `src/ui/mod.rs` — compiles on tip `f5177a7` |

Untracked/supporting: `issues.md`, build status notes, `scripts/deploy_full_usb.ps1` (disabled), UEFI `target/` artifacts (should not be released).

---

## Explicitly out of scope / not done

- Merge to `main`
- Real-disk or USB burns
- Product Linux live ISO
- Durable mapfile I/O
- Boot-media exclusion
- SpinRite lab comparison
- Public release packaging / main merge (owner approval required)

**Later same-day update:** Integrated `desktop/driverepair_desktop` read-only Python scanner + unittest suite; host `cargo test --features "std,alloc" --lib` → 42 passed / 3 ignored (exit 0) on this Windows workstation. Desktop unittest: re-run after ImageReader Windows `/dev/` path fix.

---

## Rollback

### If branch is unmerged (current expected state)

```powershell
# Discard uncommitted Gate 0 work (DESTRUCTIVE to WIP — owner only)
git checkout main
git branch -D remediation/gate0-safety-2026-10-31
# Or keep branch but reset working tree to e739636:
git reset --hard e7396368828bef08d534a1f2442d0e382243cf9e
```

### If commits exist on the remediation branch (not yet on main)

```powershell
git checkout main
git branch -D remediation/gate0-safety-2026-10-31
```

### If commits were merged to main (not done at doc time)

```powershell
git revert <merge-or-gate0-commit-sha>
# Prefer revert over hard reset on shared main
```

### USB script rollback note

Re-enabling USB scripts is an **owner approval** event, not a casual revert. Even after git rollback, do not burn media without Gate evidence.

---

## Diff observation method

At doc time: `git status` showed modified library/boot/script/CI files on `remediation/gate0-safety-2026-10-31` with HEAD still `e739636…`. Use `git diff e739636` for a full patch after commits land.
