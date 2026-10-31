# DriveRepair

DriveRepair is an experimental storage diagnostic and repair research project. Its **desktop external-disk scanner** can operate on Windows, macOS and Linux **without rebooting**. A separate experimental Rust BIOS/UEFI boot environment remains in the repository but is **not ready for real-disk repairs or public release**.

## Run a read-only external USB / portable drive scan

The current desktop utility uses **Python 3.10+** and the operating system's existing storage drivers. No Python packages are needed; raw physical-drive reads often require elevated privileges.

```bash
cd desktop
python3 -m driverepair_desktop list
# Select the exact external disk ID printed above (Linux example):
sudo python3 -m driverepair_desktop scan --device linux:/dev/sdb
# Optional complete scan; may stress a failing disk:
sudo python3 -m driverepair_desktop scan --device linux:/dev/sdb --mode full --ack-risk
```

On **Windows**, use `py -3 -m driverepair_desktop list` from an elevated PowerShell terminal in `desktop`, then `py -3 -m driverepair_desktop scan --device windows:PhysicalDriveN` using the discovered ID. On **macOS**, use `python3 -m driverepair_desktop list` and `sudo python3 -m driverepair_desktop scan --device macos:diskN` from `desktop`.

Detailed instructions, safeguards, supported buses and limitations: **[desktop/README.md](desktop/README.md)**.

## Actual capabilities

| Component | Status |
|---|---|
| Desktop external whole-disk discovery | Implemented: Linux `lsblk`, macOS `diskutil`, Windows PowerShell `Get-Disk`; cross-OS fixture tested |
| Desktop read-only USB/external surface scanning | Implemented, synthetic-image and mocked-device tested; **real-hardware validation pending** |
| Bounded sequential/sample reads, no source disk writes | Implemented in desktop scanner, synthetic tests passing |
| Large-drive memory management | Streaming chunks, fixed memory bounds (desktop path) |
| OS-level read error and short-read reporting | Implemented (not sector reconstruction or checksum proof) |
| Desktop Windows/macOS hardware compatibility | Implemented code paths; not yet validated on those operating systems |
| SMART, bad-sector recovery, SSD remediation | **Not available in desktop path** |
| BIOS/UEFI Rust boot environment | Experimental, not verified safe for public use |
| Standalone signed Windows/macOS installers | Not built or signed |

**Critical limitation:** A completed read-only scan does not establish data integrity or physical health, nor does it repair a drive. A failing drive should be cloned or professionally recovered before being stressed by diagnostics. Some USB bridges and system permissions prohibit raw disk reads. Never run the experimental boot repair code on valuable media.

## Tests

```bash
cd desktop
python3 -m unittest discover -s tests -v
python3 -m driverepair_desktop scan-image --image /path/to/a/regular/file.img --json
```

No physical disk access is required for tests. OS-specific smoke testing and hardware benchmarks are release blockers, not completed features. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Repository layout

- `desktop/driverepair_desktop/`: read-only host OS disk discovery, scanner and CLI.
- `desktop/tests/`: test fixtures and failure-mode coverage; no privileged disk I/O.
- `src/boot/`: experimental BIOS/UEFI boot prototypes (separate Cargo crates).
- `src/disk/`, `src/repair/`: experimental Rust framework; **not** a production hardware backend.
- `scripts/`: legacy boot-media scripts; **destructive USB writers are hard-disabled (exit 2) pending safety gates** and are not part of desktop scanning.

## Principles

- Never infer a repaired sector from a successful read.
- Never issue write-capable I/O from the desktop scanner.
- Default to external whole disks only, requiring an exact discovered disk ID.
- Abort when the disk identity changes, access is lost or read error limits are exceeded.
- Use independent, reproducible tests before any claims about recovery effectiveness.

**License:** MIT (see `Cargo.toml`; review third-party notices before distributing built media). Project maintained by commstech.


## Gate 0 Rust library (experimental)

Host Rust crates now fail closed on unimplemented I/O, default to read-only access, and refuse misleading SMART/repair claims. See `docs/release-readiness/` and `src/boot/EXPERIMENTAL.md`. These are **not** a substitute for the desktop scanner.

