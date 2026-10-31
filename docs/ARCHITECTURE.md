# Architecture

## Product architecture (supported)

```
Operator CLI (desktop/driverepair_desktop)
        │
        ├─ devices.py   — OS discovery (lsblk / diskutil / Get-Disk)
        │                   external whole-disk filter + stable IDs
        ├─ scanner.py   — read-only RawDevice / ImageReader
        │                   sample or full chunked reads, identity recheck
        └─ cli.py       — list | scan | scan-image (+ JSON)
```

**Key properties**

- Source path is always read-only
- Device must match a fresh discovery entry
- Errors are reported as OS-level read failures, never as “repaired”
- Tests use fixtures and regular files; physical disks are optional and operator-gated

## Experimental architecture (unsupported)

```
src/disk + src/repair + src/smart   — fail-closed stubs / parsers
src/boot/uefi + src/boot/bios       — experimental firmware prototypes
scripts/*usb*                       — hard-disabled (exit 2)
```

These modules exist for research and Gate 0 containment. They are **not** the public product surface. See `src/boot/EXPERIMENTAL.md`.

## Future directions (not claimed shipped)

- SMART / NVMe health via OS tools (`smartctl`, `nvme-cli`) behind the desktop CLI
- Image-first rescue orchestration (e.g. mapfile-based cloning) with strict source≠destination checks
- Optional signed desktop installers

Until those land with tests and clear docs, do not market them as available.
