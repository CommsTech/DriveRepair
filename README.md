# DriveRepair

**Cross-platform, read-only external disk surface scanner** for Windows, macOS, and Linux.

DriveRepair helps you discover eligible **external whole disks** and measure whether the operating system can return requested bytes—without writing to the source disk, without rebooting, and without pretending that a successful read means the data is healthy or repaired.

| | |
|---|---|
| **Status** | Public experimental (`v0.0.1`) |
| **Product path** | `desktop/` Python 3.10+ CLI |
| **License** | [MIT](LICENSE) |
| **Writes to source disks** | Never (desktop scanner) |

## What it does today

- Lists external / removable whole disks using OS tools (`lsblk`, `diskutil`, PowerShell `Get-Disk`)
- Runs **sample** or **full** read-only surface scans with bounded chunk size and error limits
- Emits human or **JSON** results (readable bytes, attempted ranges, OS read errors)
- Re-checks device identity before and after a scan
- Runs offline unit tests without touching physical disks

## What it does *not* do

- Does **not** repair, remap, TRIM, format, or wipe disks
- Does **not** recover files or reconstruct unreadable data
- Does **not** prove data integrity (a successful read ≠ correct original content)
- Does **not** ship a production BIOS/UEFI “repair USB” (those prototypes are experimental and disabled for destructive media writing)

If you need a clone of a failing drive, use a dedicated imaging tool on sacrificial or already-backed-up media. Reading a dying disk can accelerate failure—**image first**.

## Quick start

```bash
cd desktop
python3 -m driverepair_desktop list
# Use an exact ID from the list, then:
sudo python3 -m driverepair_desktop scan --device linux:/dev/sdX
```

**Windows** (elevated PowerShell):

```powershell
cd desktop
py -3 -m driverepair_desktop list
py -3 -m driverepair_desktop scan --device windows:PhysicalDriveN
```

**macOS:**

```bash
cd desktop
python3 -m driverepair_desktop list
sudo python3 -m driverepair_desktop scan --device macos:diskN
```

Full mode (longer, more stress on failing media):

```bash
sudo python3 -m driverepair_desktop scan --device <ID> --mode full --ack-risk --json
```

Hardware-free smoke test:

```bash
python3 -m driverepair_desktop scan-image --image ./some-regular-file.bin --json
```

Details, privileges, and limitations: **[desktop/README.md](desktop/README.md)**.

## Tests

```bash
cd desktop
python3 -m unittest discover -s tests -v
```

Rust library Gate 0 safety tests (fail-closed stubs; not a hardware driver suite):

```bash
cargo test --features "std,alloc" --lib
```

## Repository layout

| Path | Role |
|---|---|
| `desktop/driverepair_desktop/` | **Supported product:** read-only host scanner |
| `desktop/tests/` | Synthetic / fixture tests (no real disks) |
| `src/` | Experimental Rust library (fail-closed unimplemented I/O) |
| `src/boot/` | Experimental UEFI/BIOS prototypes — **unshipped** |
| `scripts/` | Legacy USB writers — **hard-disabled** (`exit 2`) |
| `docs/` | Status, architecture, safety, and release notes |

## Documentation

- [Project status](docs/PROJECT_STATUS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Safety gate](docs/release-readiness/SAFETY_GATE.md)
- [Test evidence](docs/release-readiness/TEST_EVIDENCE.md)
- [Release decision](docs/release-readiness/RELEASE_DECISION.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Principles

1. Never call a successful read a “repair.”
2. Never write to the scanned source from the desktop path.
3. Prefer explicit device IDs from a fresh discovery list.
4. Prefer honest `Unknown` / `Unsupported` over false success.
5. Publish only claims backed by tests or labeled limitations.

## Disclaimer

THE SOFTWARE IS PROVIDED “AS IS”. DriveRepair is experimental diagnostic software. Authors are not liable for data loss, drive failure, or misuse. Always keep backups.

Maintained by **commstech**.
