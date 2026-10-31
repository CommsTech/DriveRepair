# Project status

**Public classification:** Experimental open-source diagnostic tool  
**Version:** 0.0.1  
**Supported product:** Desktop read-only external disk scanner (`desktop/`)

## Working today

| Capability | Evidence |
|---|---|
| External disk listing (Win/macOS/Linux code paths) | Implemented; fixture-tested |
| Read-only sample/full scans | Implemented; synthetic tests passing |
| JSON reporting of read errors | Implemented |
| Device identity recheck | Implemented; unit-tested |
| Offline unit tests without physical disks | `python -m unittest` in `desktop/tests` |
| Rust Gate 0 fail-closed library tests | `cargo test --features "std,alloc" --lib` |

## Not available / not claimed

- Sector repair, remapping, TRIM, secure erase
- File recovery or verified reconstruction of unreadable data
- Production BIOS/UEFI bootable repair media
- Signed installers
- Guaranteed SMART/NVMe health reporting
- Image-first clone/rescue engine (scaffold only)

## Release gates

| Gate | Status |
|---|---|
| Honest public docs + MIT LICENSE | Met for experimental release |
| Desktop synthetic tests green | Met on maintainer workstation / CI config present |
| Hardware matrix on sacrificial externals | Pending (community / maintainer lab) |
| Write-capable remediation | Out of scope until separately designed and audited |

## Recommended public messaging

> DriveRepair is an experimental, open-source, **read-only** external disk surface scanner for Windows, macOS, and Linux. It reports whether the OS can read requested regions. It does not repair drives.
