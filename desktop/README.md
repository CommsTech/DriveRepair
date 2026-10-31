# DriveRepair Desktop

**Public experimental** read-only external disk surface scanner for Windows, macOS, and Linux.

Discovers *external whole disks* with built-in OS utilities, then reads sectors through a **read-only** OS handle. No reboot required.

This tool **does not** repair sectors, recover files, validate content correctness, unlock encrypted volumes, or write to the source disk. A successful scan only means the OS returned bytes for the requested ranges.

## Requirements

- Python **3.10+** (standard library only)
- Elevated privileges for most raw physical-disk reads
- Windows 10/11, recent macOS, or Linux with `lsblk`

## Commands

```bash
cd desktop
python3 -m driverepair_desktop list
sudo python3 -m driverepair_desktop scan --device <ID-from-list>
sudo python3 -m driverepair_desktop scan --device <ID> --mode full --ack-risk --json
python3 -m driverepair_desktop scan-image --image ./file.bin --json
```

Windows (elevated PowerShell): use `py -3 -m driverepair_desktop …` with `windows:PhysicalDriveN` IDs.

macOS: use `macos:diskN` IDs; raw reads use `/dev/rdiskN` read-only.

## Tests

```bash
cd desktop
python3 -m unittest discover -s tests -v
```

## Packaging note

Optional PyInstaller builds are unsupported until signed per-OS artifacts are published. Prefer running from source for now.
