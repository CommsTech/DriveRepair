# DriveRepair Desktop — external drive scans without reboot

**Experimental read-only scanner** for Windows, macOS, and Linux. It discovers *external whole disks* using built-in OS utilities, then reads disk sectors from a **read-only** operating-system handle. Works on USB external HDDs, SSDs and thumb drives when the OS exposes a physical disk; other external buses are supported only when positively identified by the OS.

This scanner **does not repair sectors, recover damaged data, interpret file systems, validate data integrity, unlock encrypted disks, or require booting from a USB stick.** It reports OS-level read failures. A successful scan is **not** proof of drive health or data correctness. Reading a failing disk repeatedly may worsen its condition: **image valuable data first**.

## Requirements

- Python **3.10+**; only Python standard library used; no `pip install` required.
- **Windows 10/11:** PowerShell `Get-Disk` (Storage module), Administrator privileges for raw physical-device reads; disk access subject to Windows device policy.
- **macOS:** `diskutil`, and typically `sudo` for raw `/dev/rdiskN` access. macOS security policy may disallow reads on busy disks.
- **Linux:** `lsblk` (util-linux), and typically `sudo` / block-device permission. Encrypted or virtual disks, network mounts, and internal disks aren't admitted by default.

Read only: no unmounts, ejects, TRIM/discard, formatting, write handles, automatic repair, filesystem modification or service installation.

## Run

From the repository's `desktop/` directory:

```bash
# List eligible external physical disks
python3 -m driverepair_desktop list

# Scan 128 evenly spaced 1MiB regions (sample; not exhaustive)
# Select an exact ID from the prior list.
sudo python3 -m driverepair_desktop scan --device linux:/dev/sdb

# Read the entire external disk; might take hours and increase wear
sudo python3 -m driverepair_desktop scan --device linux:/dev/sdb --mode full --ack-risk

# No hardware required: test scan of a regular disk image
python3 -m driverepair_desktop scan-image --image ./test.img --mode full --json
```

On **macOS** use `python3 -m driverepair_desktop list` then select an exact `macos:diskN` ID, scanning with `sudo python3 -m driverepair_desktop scan --device macos:diskN`. The scanner opens `/dev/rdiskN` **read-only**.

On **Windows** use an elevated PowerShell terminal:

```powershell
cd desktop
py -3 -m driverepair_desktop list
py -3 -m driverepair_desktop scan --device windows:PhysicalDrive2
py -3 -m driverepair_desktop scan --device windows:PhysicalDrive2 --mode full --ack-risk --json
```

`scan` never accepts a bare user-provided raw device path: it must match a fresh external disk discovered by the OS. Device identity is rechecked before and after scanning. Logical sector size is used to align reads. Scans stop after 16 bad chunks by default (`--max-errors`). A failed 1MiB chunk does **not** prove every sector in that chunk is bad.

## Tests (no access to physical disks)

```bash
cd desktop
python3 -m unittest discover -s tests -v
python3 -m driverepair_desktop scan-image --image path/to/synthetic-image.img --json
```

Cross-platform enumeration and OS-specific raw-drive access have **not been validated on all hardware**. Unsupported device types are excluded rather than implicitly treated as safe. Python system calls may require administrative permission or be denied on mounted, active or protected disks. Live file-system activity can change read results during a scan.

## Packaging

For future per-OS native binaries, build on the **same target OS** using PyInstaller (optional third-party packaging dependency):

```bash
cd desktop
python3 -m pip install pyinstaller
pyinstaller --onefile --name DriveRepair-desktop launch.py
```

This is a packaging recipe, not evidence that Windows/macOS executable artifacts have been tested or signed. No physical-drive modifications should be added to this desktop reader without a separate audited design and approval.
