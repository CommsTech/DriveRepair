# DriveRepair desktop — 0.3.0b1

A privacy-first guided Python 3.10+ desktop UI/CLI, with incremental Rust recovery-core migration. This is not a signed standalone native installer. The GUI requires Tk. Raw-device repair remains experimental; do not operate on irreplaceable disks.

## Install and launch

```sh
python3 -m pip install .
python3 -m driverepair_desktop gui
# or: driverepair-gui
python3 -m driverepair_desktop --help
```

Native Rust regular-image rescue core (OPTIONAL):

```sh
cargo build --release --manifest-path ../rust/recovery-core/Cargo.toml
export DRIVEREPAIR_RUST_CORE=/path/to/driverepair-recovery-core
python3 -m driverepair_desktop rescue-image --engine rust --image original.img --output new.img
```

Rust core is experimental; no raw devices and no Windows Rust resume. Default Python engine remains the better-tested reference until CI/hardware comparisons establish parity. Rust `.rmap` is not compatible with Python `.rescue.json`.

## Safe recovery shortcuts

```sh
# Fast, bounded read-only triage. Sampled areas ONLY.
python3 -m driverepair_desktop list --json
python3 -m driverepair_desktop scan --device linux:/dev/sdX --mode triage --samples 128
# First-pass image rescue + focused retries (separate output drive required).
python3 -m driverepair_desktop rescue-image --image source.img --output recovered.img --multi-pass
# Preview BEFORE restoring; IDs are sourced from the current image.
python3 -m driverepair_desktop list-deleted-fat32 --image recovered.img --json
python3 -m driverepair_desktop undelete-fat32 --image recovered.img --file-id ID --output-dir newly-created-folder
# Optional The Sleuth Kit, for additional filesystems; image only.
python3 -m driverepair_desktop list-deleted-tsk --image recovered.img --offset-sectors 0 --json
python3 -m driverepair_desktop recover-selected-tsk --image recovered.img --offset-sectors 0 \
  --file-id ID --output-dir newly-created-folder
# Evidence hash report, privacy-minimized and not a forensic certification.
python3 -m driverepair_desktop evidence-image --image recovered.img --output new-evidence.json
# Scheduled SMART trend check, no automatic repairs.
python3 -m driverepair_desktop monitor-external --device linux:/dev/sdX \
  --expect-fingerprint 12HEXCHARS --state /healthy-storage/history.json
# Multi-FS detect + unified recover (FAT32/NTFS/exFAT undelete; else RAW carve).
python3 -m driverepair_desktop detect-filesystems --image recovered.img --json
python3 -m driverepair_desktop recover-image --image recovered.img --output-dir newly-created-folder --mode auto
# Optional soft indicators during refresh (WATCH/STOP only; latency/SMART stay primary).
python3 -m driverepair_desktop refresh-external --device windows:N --journal D:\journals\job \
  --ack-risk --ack-destructive --ack-no-backup --ack-data-loss-risk \
  --ack-usb-bridge-risk --ack-unvalidated-hardware --confirm-identity 12HEXCHARS \
  --acoustic-watch --shock-guard --smart-deltas
```

Both deleted-file backends only return *candidates*, not guaranteed original content; FAT32 assumes a contiguous unallocated extent and does not restore overwritten bytes. TSK support depends on available `fls` and `icat` binaries and their filesystem parser support. Source disks and images are read-only in recovery paths. Destination must be a new path. Acoustic/IMU sensors are soft chassis signals, not platter wear meters.

GUI: choose a goal on the **Start here** tab, or open **Recover deleted files** for multi-selection. External drive list includes model/size/transport/location and an identity hint. Media-refresh operations remain separately gated and experimental.

## Optional system utilities

- `smartctl` (smartmontools) for SMART and NVMe health.
- `e2fsck` (e2fsprogs) for read-only ext checks or clone-only repair.
- `fls` / `icat` (The Sleuth Kit) for metadata-assisted deleted-file recovery.
- Cargo/Rust stable for the optional standalone image rescue core.

Physical USB-docked recovery on Windows/macOS, custom BIOS/UEFI boot ISO, 7-pass/DoD-certified erasure, firmware rescue and automated media refresh **are not validated/implemented**. See `../docs/PUBLIC_BETA_GATES.md` for release blockers and `../docs/ARCHITECTURE_CURRENT.md` for Rust migration.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 ../scripts/build_desktop.py
```
