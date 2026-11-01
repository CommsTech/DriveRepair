# DriveRepair

**Experimental desktop drive diagnostics, image-first rescue, filesystem-aware undelete, and clone-only repair toolkit.**

DriveRepair is intended to grow into a single desktop/bootable workflow for inspecting drives, rescuing readable sectors, recovering files, repairing filesystems, assessing media reliability and measuring maintenance outcomes. **It does not yet do all of those things**. The current supported desktop CLI runs from Python 3.10+ without rebooting; the historical Rust BIOS/UEFI code remains experimental and is not the desktop recovery engine. A Tkinter graphical interface now connects the supported desktop features.

**Release status: 0.2.9b1 BETA CANDIDATE — PRIVATE TEST ONLY.** This implementation has synthetic unit tests but no validated Windows/macOS physical-device rescue, no physically failing-disk recovery benchmarks and no verified firmware-level remediation.

## Install and run (desktop, without restarting)

```bash
cd desktop
python -m pip install .
python -m driverepair_desktop gui
# or: driverepair-gui
```

`tkinter` may require your OS Python/Tk package. Windows and macOS can use regular-file recovery and read-only external-drive scanning; Linux also has experimental physical-disk image rescue.

## Implemented desktop commands

| Command | What it currently does | Source writes |
|---|---|---|
| `list` | Enumerate eligible external whole disks | None |
| `health` | Optional `smartctl` SMART/NVMe health snapshot without self-tests | None |
| `scan` / `scan-image` | Read-only sample/full diagnostics | None |
| `rescue-image` | Clone readable regions of a regular-file disk image to a new sparse image; journal/resume/targeted retry | None |
| `rescue-external` | **Linux only, experimental:** rescue selected external whole disk into a regular-file image on a different verified storage device | None to raw patient; destination written |
| `benchmark-image` / `benchmark-external` | Read throughput, percentile latency and slow-zone measurements | None |
| `compare-benchmarks` | Compare two same-source benchmark JSON files; *does not prove improved lifespan* | None |
| `carve-image` | Extract intact PNGs with CRC checks; best-effort JPEGs from disk images | None to image; output files created |
| `undelete-fat32` | Recover contiguous, apparently unallocated FAT32 deleted files; names/content unverified | None to image; output files created |
| `verify-images` | Byte-compare a stable source image and recovered image; report SHA-256/mismatches | None |
| `check-ext-image` | Non-modifying ext2/3/4 filesystem check through e2fsck | None |
| `repair-ext-image` | Clone ext filesystem image and run e2fsck repair on **the copy** | None to original; copy modified |
| `salvage-zip` | Recover CRC-valid, intact ZIP members even if other ZIP members are corrupt | None to archive; output files created |
| `ram-journal-check` | Read-only check of Linux tmpfs + local UPS/battery readiness for optional volatile journaling | None |
| `refresh-image` / `refresh-external` | **In-Place Media Refresh (experimental):** rolling journal `SAVED→WRITING→VERIFIED→COMMITTED`; `--mode adaptive` (default) or `full`; skips unreadable/inconsistent regions | **Writes patient media** after multi-flag acknowledgement; journal holds only the active region |

**Not yet implemented:** NTFS/exFAT/APFS/ext4 undelete, fragmented FAT32 recovery, whole-disk partition-table repair, damaged-file reconstruction without redundancy, proven hardware media rejuvenation, physical-wear reversal, native signed installers, and a fully integrated modern bootable environment. In-place refresh is experimental and does **not** claim wear reversal. The desktop GUI is present but needs real-platform testing. Optional `health` uses local `smartctl` when present; absence or `unknown` does not mean healthy.

## Get started

```bash
cd desktop
python3 -m unittest discover -s tests -v
python3 -m driverepair_desktop --help
python3 -m driverepair_desktop list
python3 -m driverepair_desktop health --device linux:/dev/sdX --json
python3 -m driverepair_desktop benchmark-image --image /path/to/test.img --json
python3 -m driverepair_desktop rescue-image --image /path/to/test.img --output /safe/different/path/rescue.img --json
python3 -m driverepair_desktop carve-image --image /safe/path/rescue.img --output-dir /safe/path/carved --json
python3 -m driverepair_desktop salvage-zip --archive damaged.zip --output-dir recovered-members
```

For rescue after incomplete reads, use `rescue-image --resume --retry-missing` with the exact same source/image/output/chunk size. The `.rescue.json` map records unknown ranges. **A zero byte in a sparse rescue image might mean an unreadable/unattempted sector, not recovered original data. Always examine the map.**

Never put a recovery destination on the drive being rescued. By design the Linux live-device command refuses destinations that cannot be verified as separate block-device storage. Image-based workflows run on Windows, macOS and Linux; physical-device acquisition on Windows/macOS needs additional work.

See [desktop guide](desktop/README.md), [project status](docs/PROJECT_STATUS.md), and [media recovery research](docs/MEDIA_REFRESH_RESEARCH.md).

## Safety

- Diagnostics and rescue use read-only source handles. All writes go to **new output files**.
- Default recovery commands do not rewrite physical sectors. `repair-ext-image` repairs a **new output copy** using optional `e2fsck`.
- `refresh-external` / `refresh-image` are a dedicated In-Place Media Refresh mode alongside image recovery—not a replacement for it. `refresh-external` requires a **disk-backed, separate-storage journal** and explicit acknowledgements (including `--ack-unvalidated-hardware`). It aborts on write/read-back failure without discarding the original bytes, and refuses to rewrite unreadable/inconsistent regions. A Linux-only, explicitly volatile `ramdisk` option requires verified RAM filesystem, battery/UPS telemetry, separate dock-power acknowledgment, and accepts host-crash data-loss risk. This is a **private experimental hardware feature**, not a full backup or public-release-certified remediation tool.
- Read errors can be recoverable later; continued reads and SMART queries can stress or wake a mechanically failing drive. For valuable failing media, professional recovery or a proven imaging tool may be preferable.
- Image-first recovery does not magically reconstruct lost data or reverse wear. The user must verify backups and destination identity.
- **This code has not undergone physical-hardware validation or security review sufficient for public release.**

## Historical components

`src/` and `src/boot/` contain earlier Rust prototypes. They are intentionally not invoked as hardware-repair drivers by the desktop CLI. The legacy USB writers under `scripts/` remain hard-disabled for safety.

## License

MIT, see [LICENSE](LICENSE). No third-party recovery engine is copied or bundled.

## 0.2.9b1 preview — faster scanning and volatile RAM journaling

**Do not run in-place refresh on irreplaceable media.** Discover a disk with `driverepair list --json`, compare model/size/masked serial, and use the current `identity_hint` in `refresh-external --confirm-identity`. Device paths can change when a USB dock reconnects; never copy a remembered `PhysicalDriveN` or `/dev/sdX` from another session.

To check a Linux RAM journal without writing a disk:

```sh
# Prepare a temporary RAM filesystem with no swapping, if the host/kernel supports it.
sudo mkdir -p /mnt/driverepair-ram
sudo mount -t tmpfs -o size=256M,noswap,mode=0700 tmpfs /mnt/driverepair-ram
python -m driverepair_desktop ram-journal-check \
  --journal /mnt/driverepair-ram/job001 --power-source nut:myups --chunk-mib 8
```

A locally connected, USB-managed Network UPS Tools device must report `OL`, at least 70% charge, and at least 15 minutes expected runtime. A Linux laptop battery can use `--power-source battery` while not discharging and at least 80% charged. Power checks repeat during the session. These signals **do not prove** that the external disk and USB dock share battery backup. UPS-backing does not prevent application crashes, USB bridge resets, hardware failure, or kernel crashes. A tmpfs journal survives process exits but **not** host reboot or loss of RAM; do not confuse it with a backup. If system swap is active, a tmpfs mount lacking `noswap` will be rejected. RAM journaling is disabled for physical writes on Windows/macOS until RAM-disk and battery behavior are validated there. For physical disks, durable disk journaling is still the default and recommended choice.

`refresh-external` requires additional deliberately verbose risk acknowledgements and is a private lab capability. For synthetic testing use `refresh-image` on a throwaway image. The `--chunk-mib` option supports 1–64 MiB; the best setting needs measured per-device throughput and fault-injection results. Larger regions reduce metadata and fsync frequency but raise the amount of original data simultaneously at risk. The desktop recovery engine is currently **Python**, not an optimized Rust driver; the Rust boot source is separate and unverified.

See [Release audit and beta gate](docs/release-readiness/BETA_CANDIDATE_0.2.9.md).
