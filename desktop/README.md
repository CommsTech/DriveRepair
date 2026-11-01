# DriveRepair desktop (0.2.7, experimental)

DriveRepair provides a **native-desktop graphical interface** and a programmable CLI on Python 3.10+ for Windows, macOS and Linux. It runs **without rebooting**. The interface is Tk (`tkinter`, included in many Python installs but an extra OS package on some Linux distributions). It is not a signed Windows `.exe`, macOS `.app`, or bootable ISO.

## Install and launch

```bash
cd desktop
python -m pip install .
python -m driverepair_desktop gui
# or: driverepair-gui
```

Run with `python3` on systems where `python` is Python 2 or not present. If Tk is unavailable, use `python -m driverepair_desktop --help` (no GUI dependency is required for the CLI). Linux packages may call Tk `python3-tk`. You can also run directly from this folder without installation.

## Functional capabilities

| Command | Result | Writes source disk? | Prerequisites / limits |
|---|---|---|---|
| `list` | Enumerate conservatively filtered external physical whole disks | No | Host OS discovery tools |
| `scan` | Read-only sampled/full external-disk scans | No | OS disk read permission |
| `health` | SMART/NVMe device-health snapshot | No | Optional `smartctl`; drive/bridge support varies |
| `benchmark-external` | Sampled/full read performance | No | Explicit acknowledgment; can stress failing media |
| `rescue-external` | Image readable regions of external disk | No to source | **Linux only**; separate physical destination verified |
| `scan-image` | Readability scan of a regular-file image | No | Any supported desktop OS |
| `rescue-image` | Sparse image rescue, journal, resume, bounded retry | No | New destination image, same source on resume |
| `verify-images` | Byte-for-byte comparison and SHA-256 against stable original file | No | Original source file must still be readable/stable |
| `benchmark-image` | Regular-image read metrics | No | Cache affected |
| `carve-image` | PNG CRC-validated / heuristic JPEG carving | No | May include undeleted or fragmented content |
| `undelete-fat32` | Recover plausible contiguous FAT32 deleted files | No | Raw FAT32 volume or MBR FAT32 partition image |
| `salvage-zip` | CRC-validated intact ZIP members | No | ZIP central directory still readable |
| `check-ext-image` | `e2fsck -f -n` read-only ext2/3/4 filesystem check | No | `e2fsck` from e2fsprogs installed |
| `repair-ext-image` | Clone ext2/3/4 image and run `e2fsck -f -y` on the **clone only** | No | `e2fsck`, new path, `--ack-repair` |

**Critical distinction:** Undelete is *speculative*. FAT32 directory entries preserve the size and starting cluster, but not the first filename character. A contiguous unallocated region can already have been overwritten or may originally have been fragmented. Every file is marked **UNVERIFIED**. Recovered image sectors likewise are not independently correct unless compared to known-good hashes/data.

## Examples

```bash
python -m driverepair_desktop list
python -m driverepair_desktop scan --device linux:/dev/sdX --mode sample --json
python -m driverepair_desktop rescue-image --image input.img --output rescued.img --json
python -m driverepair_desktop rescue-image --image input.img --output rescued.img --resume --retry-missing --json
python -m driverepair_desktop verify-images --image input.img --output rescued.img --json
python -m driverepair_desktop carve-image --image rescued.img --output-dir recovered_photos --json
python -m driverepair_desktop undelete-fat32 --image fat32.img --output-dir deleted_files --json
python -m driverepair_desktop salvage-zip --archive broken.zip --output-dir valid_members --json
python -m driverepair_desktop check-ext-image --image ext4_volume.img --json
python -m driverepair_desktop repair-ext-image --image ext4_volume.img --output ext4_repaired_copy.img --ack-repair --json
```

Use **IDs reported by `list`**, not a guessed device path. `rescue-external` currently requires a separately mounted physical destination on Linux and fails closed on unsupported storage layouts. Windows/macOS physical-disk rescue is **not implemented**; image-based recovery and external-disk scans are available without restarting.

## Safety and fidelity

- **`refresh-external` is a destructive, separately authorized experimental mode** that opens the patient for writing. It is **NOT** enabled by read-only diagnostics and **NOT** a substitute for backup. It requires explicit risk acknowledgements, separate-disk durable journal (`--journal-backend disk`), identity checks, exclusive access where supported, and read-back verification. macOS raw refresh is disabled pending safe exclusive-locking support. Windows/Linux live fault-injection validation is incomplete. Do not use on irreplaceable data.
- Clone-based filesystem repair modifies a **newly created image copy**, never the original.
- Any attempt to recover an unstable drive adds read stress. When the data is irreplaceable or the drive makes mechanical noises, consult a professional before repeated scans/retries.
- The `.rescue.json` journal is required to interpret missing/sparse sectors. **A zero in a sparse rescue output is not evidence of successfully recovered zeroes**. `verify-images` explicitly refuses incomplete recovery journals.
- A byte-exact comparison to a known source image is not evidence that the original media was free of corruption.
- The ext repair command only accepts *unpartitioned ext filesystem images*. It rejects partitioned whole-disk images; do not use it on mounted or active block devices. `e2fsck` repair can discard inconsistent metadata or file references **on the copy**. Preserve the original, the map, and any available backups.
- No deleted-file recovery claims apply to APFS, exFAT, NTFS, ext4, or fragmented FAT32 files at this stage. ZIP salvage needs a usable central directory.
- These are software tests and simulated media; actual desktop/raw-hardware validation is still outstanding.

## Tests/build

```bash
cd desktop
python -m unittest discover -s tests -v
python -m compileall -q driverepair_desktop
python -m pip wheel . --no-deps -w dist
```

The `.whl` is portable Python, **not** a native bundled executable. Windows, Linux and macOS should each undergo physical hardware compatibility and GUI smoke tests before public release.

## In-place refresh (experimental; not public-release ready)

`refresh-image` allows a synthetic regular-file test. `refresh-external` attempts original-disk writes only after strict checks; do not test on valuable disks. The rolling journal preserves **one region** on a healthy separate disk, normally 1 MiB, without requiring a 12 TB full image. A journal is **not a backup** against total failure of the source.

The journal defaults to `disk` and retains original bytes through `SAVED → WRITING → VERIFIED → COMMITTED`. The job stops on any failed write/readback, preserving the active region and its digest for a future resume. On interrupted jobs **never delete `region.bin` or `meta.json`**. Only a clean `completed` run may auto-delete its journal.

Use `--journal-backend disk` for physical media. The RAM-only backends are synthetic/image-testing conveniences and cannot survive power loss mid-write. A source disk with mounted partitions/holders must be detached before even considering physical refresh. USB docks can drop connections or report unstable identity: this build remains unvalidated on real hardware under power loss or hot-unplug.

A `completed_with_skips_or_verify_failures` or `completed_with_probe_errors` status is **not success** and returns a nonzero code. Unreadable areas are never filled with invented bytes. Journal/disk storage failures abort the operation.
