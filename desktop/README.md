## No image required: targeted in-place repair (experimental)

The **Diagnose / Rescue** page now shows **Quick repair**, **Full repair**,
and a **Temporary region storage** choice. Set **Volatile RAM only (NO saved
files)** when a second storage destination is unavailable and you explicitly
accept that losing RAM during a write can destroy source data. This does not
save a rescue image or a rolling-journal file. **Disk journal** remains safer.

Run `refresh-external --mode full --journal-backend memory` from the CLI for a
whole-surface rewrite, or select **In-place refresh** in the GUI. Both require
all appropriate device identity and destructive-operation confirmations.
SMART warnings, unreadable data and uncertain data remain stop conditions
rather than targets for speculative repair. On Windows an offline patient
and elevated privileges are necessary; on macOS raw writes remain disabled.
See `../docs/NO_IMAGE_RAM_REPAIR.md` for exact commands and limitations.

# DriveRepair desktop — 0.3.3b4

A privacy-first guided Python 3.10+ desktop UI/CLI, with incremental Rust recovery-core migration. This is not a signed standalone native installer. The GUI requires Tk. Raw-device repair remains experimental; do not operate on irreplaceable disks.

## Recovery progress for large sparse images

`rescue-status --output IMAGE --json` reports committed progress from the
`IMAGE.rescue.json` journal. A 256 GB image can report a 256 GB logical length
immediately after creation, even when only 1% is copied. Never use file length
to decide a recovery succeeded; check `clean_rescue_complete` and separately
verify the recovered file contents. Lab scripts no longer automatically start
in-place refresh. See `../docs/RESCUE_PROGRESS_AND_LAB_SAFETY.md`.

## Image integrity and targeted hash-verified repair

The **Integrity / bit errors** GUI page and `integrity-baseline`, `integrity-audit`,
and `integrity-restore-copy` commands add SHA-256 reference chunk checking and
optional restoration of mismatched chunks from a separately verified source into
a **NEW output image**. The original remains untouched. Newly computed hashes
are **not** evidence that already-corrupt original data was correct. An incomplete
rescue map produces unknown chunks rather than falsely labeling holes as flipped bits.

Triage scans may use `--compare-suspects` to reread a bounded number of
suspicious regions and flag inconsistent results (correct bytes remain unknown).
Read [the data integrity guide](../docs/INTEGRITY_RECOVERY.md) before relying
on results. No physical-media bit correction was added.

## New recovery dashboard

The standard graphical interface now displays an always-visible status/progress
strip, four recovery metrics, a compact activity map and destination-space
warnings during **image rescue, Linux external rescue and Linux live-USB
system-drive rescue**. By default, technical log messages are folded away; use
**Advanced details / engine log** when investigating a problem. The controls on
all workflow tabs scroll on small laptop displays, while Stop/Save report/Open
destination remain accessible at the bottom of the application window.

To rescue a disk image, open **Image recovery**, select the source and NEW output
file, and click **Rescue**. An incomplete job can be continued using **Resume**.
After a complete first pass with missing regions, use **Retry gaps**; the
original bytes from a failing source are never invented. A resumed image's
recovery map remains `OUTPUT.rescue.json` until you explicitly choose to keep
or remove it. The GUI never automatically deletes recovery images.

The disk map is approximate and shows **scanned/read regions** rather than
certifying media health: green means bytes were read and saved, red indicates
unreadable regions, blue indicates a partially covered segment, and dark means
unscanned. A 100% first-pass indicator during retries does **not** mean all
bytes were recovered. The calculated ETA covers the forward pass only; retries
have no reliable ETA. Destination free-space estimates may be inaccurate for
sparse images or remote-share quotas. Confirm the saved result with image
verification and a filesystem check on a **copy** before relying on it.

New CLI progress options for the Python rescue engine:

```sh
# Human-readable, compact terminal progress by default
python3 -m driverepair_desktop rescue-image --image source.img --output new.img --multi-pass
# Machine-readable progress (stderr JSONL), with final result on stdout
python3 -m driverepair_desktop rescue-image --image source.img --output new.img \
  --progress-jsonl --no-live-dashboard --json
```

The optional Rust rescue-image executable remains experimental and has not yet
been integrated with this Python progress protocol; no claim of Rust/OS/hardware
performance parity is made. Native Windows/macOS hardware testing and BIOS/UEFI
boot validation remain separate release gates.

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

## Recover an unbootable internal disk (Linux live USB)

Boot a trusted Linux live USB, connect healthy destination storage, then use
GUI → **Recover OS drive** (guided selection, destination preflight, read-only
rescue) or:

```sh
python3 -m driverepair_desktop list-all-linux --json
python3 -m driverepair_desktop plan-system-recovery --device linux:/dev/sdX \
  --expect-fingerprint 12HEXCHARS --output /mnt/separate-storage/patient.img --json
python3 -m driverepair_desktop rescue-system --device linux:/dev/sdX \
  --expect-fingerprint 12HEXCHARS --output /mnt/separate-storage/patient.img \
  --ack-risk --ack-offline-system --multi-pass --json
```

This is not enabled for mounted active OS disks. `list` remains external-only.
Separate destination support includes mounted NAS shares with recognized
filesystems. Read `../docs/ONE_DRIVE_RECOVERY.md` before touching valuable data.

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

Physical USB-docked recovery on Windows/macOS, boot-tested BIOS/UEFI boot ISO, 7-pass/DoD-certified erasure, firmware rescue and automated media refresh **are not validated/implemented**. See `../docs/PUBLIC_BETA_GATES.md` for release blockers and `../docs/ARCHITECTURE_CURRENT.md` for Rust migration.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 ../scripts/build_desktop.py
```

## No second disk? Experimental emergency option

For a single internal HDD with no image destination, `refresh-system` permits
**an explicitly consented in-place adaptive rewrite of consistently readable
regions only**, from a trusted Linux live USB. The rolling journal can reside
in a verified `tmpfs` RAM mount with protected power. It does not recover
unreadable sectors, restore accidentally deleted files, or replace a backup;
loss of host RAM during a write may permanently destroy the active region.
Start in GUI → **Recover OS drive → Last resort**. See
[`../docs/ONE_DRIVE_RECOVERY.md`](../docs/ONE_DRIVE_RECOVERY.md) for required
checks and exact CLI flags. The experimental feature is not approved for
irreplaceable data or automatic operation.

### Graphical workflow controls (0.3.3b5)

Run `python -m driverepair_desktop gui`, or `python DriveRepair-0.3.3b5.pyz gui`.
The **Start here** buttons navigate to their named workflow pages; select a disk
row before Quick scan, SMART, or Rescue in **Diagnose / Rescue**. Windows and Linux
external raw-disk rescue require an independently verified destination and elevated
access; they remain unvalidated on physical hardware in this release. The recovery dashboard
is hidden while idle to leave room for the workflows. Toggle **Show recovery
dashboard** to reveal it; the dashboard appears automatically during a job.

When running the portable `.pyz`, GUI child recovery jobs execute using the
same `.pyz` rather than requiring a separate installed Python package.
If an unexpected button callback fails, DriveRepair displays an error and
records details in **Advanced details / engine log** instead of doing nothing.

Run GUI integration tests on Linux with a display:

```bash
cd desktop
xvfb-run -a python -m unittest discover -s tests -p test_gui_workflows.py -v
```

These tests use synthetic disk-image files only; they do **not** open patient
block devices or validate raw-drive writes. Windows/macOS still require real
user-interface and physical-device qualification before release.

### Scan-to-repair and dashboard (0.3.3b5)

Quick/Full repair now distinguish isolated read errors from unstable drive communication.
Balanced mode investigates error locations with a strict retry/split budget; it never
rewrites bytes that still cannot be read consistently. Preserve mode restricts work
to consistently readable slow regions. SMART media WARN requires additional explicit
authorization; critical media/transport states still prevent writes.

The recovery dashboard displays **Bytes read**, **Read errors**, **Current speed**,
and **Time remaining** during scans, then **Bytes rewritten / verified** while
refreshing. Quick-scan ETA means remaining **sample work**, not time for an entire
full-drive scan. The map has a visible color legend for each state. Unscanned
regions are not declared good.

Run `xvfb-run -a python -m unittest discover -s tests -v` on Linux to include
Tk GUI telemetry/legend tests; Windows and macOS GUI/hardware checks remain pending.
