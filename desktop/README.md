# DriveRepair Desktop (experimental)

Standard-library Python 3.10+ CLI; optional smartctl executable for health snapshots. Windows, macOS and Linux **do not need a reboot** for supported scanning, read benchmarks, image rescue, image carving and ZIP salvage. Only **Linux** currently permits experimental rescue from a real external disk, with mandatory read-risk acknowledgment and destination-block-device separation checks. Elevated privileges are usually needed for raw-disk reads.

## Commands

```bash
cd desktop
python3 -m driverepair_desktop list
python3 -m driverepair_desktop health --device linux:/dev/sdX --json  # requires smartctl
python3 -m driverepair_desktop scan --device linux:/dev/sdX --mode sample
python3 -m driverepair_desktop benchmark-external --device linux:/dev/sdX --ack-risk --json > before.json
python3 -m driverepair_desktop rescue-external --device linux:/dev/sdX --output /mnt/other-disk/recovered.img --ack-risk --json
python3 -m driverepair_desktop rescue-image --image disk-original.img --output disk-copy.img --json
python3 -m driverepair_desktop rescue-image --image disk-original.img --output disk-copy.img --resume --retry-missing --json
python3 -m driverepair_desktop carve-image --image disk-copy.img --output-dir carved-files --json
python3 -m driverepair_desktop salvage-zip --archive damaged.zip --output-dir recovered-zip-files --json
python3 -m driverepair_desktop compare-benchmarks --before before.json --after after.json
```

SMART mode reads telemetry, does not start drive self-tests, but can wake sleeping drives. A passed SMART flag is not proof of perfect health.

Substitute the **real discovered identifier**, never blindly type `/dev/sdX`. On Windows use `py -3 -m driverepair_desktop`; identifiers resemble `windows:PhysicalDrive2`. On macOS use `python3` and identifiers resemble `macos:disk4`.

**For live rescue on Linux**, the destination must be a **new regular file on a physically separate mounted block device**. The command verifies sysfs ancestry and fails closed if it cannot prove separation (for example network, tmpfs or unsupported mapping). The system drive may be the destination if distinct and sufficiently large. There is no direct disk-to-disk cloning mode.

## Recovery data interpretation

- The journal `<output>.rescue.json` is mandatory. `cursor` marks completed first-pass acquisition, `missing_ranges` contains unreadable/unverified extents, and `retry_pending_ranges` contains still-unattempted targeted retries.
- `completed` means the operating system returned bytes for all requested ranges. It is **not** an end-to-end correctness proof without original hashes or other independent validation.
- `completed_with_missing_data` means the output image is **incomplete**. Sparse holes are typically zero when read, but **must never be reported as recovered zeros**.
- `retry_in_progress` or `in_progress` indicates a resumable partial operation, provided the same source identity remains accessible.
- The first pass prioritizes easy-to-read regions; failed chunks remain unknown until an explicitly requested targeted retry, which uses bounded subdivision. This is not yet benchmarked against established tools.
- Image source identity includes filesystem metadata; modifications to the source cause resume to refuse stale journals.

## Carving/ZIP limitations

- PNG carving validates per-chunk CRC and IEND, but **does not reconstruct damaged chunks** or prove an image is visually correct.
- JPEG carving looks for a start signature and end marker; embedded markers or fragmentation can produce false positives.
- Carving may find files still present in a filesystem as well as deleted files. It does not recover original names, folder structures or fragmented file chains.
- ZIP salvage requires an intact central directory and checks individual member CRCs. It cannot recover members when the central directory is lost. ZIP member filenames are sanitized and flattened to avoid traversal.
- All output directories are newly created; no existing destination is overwritten.

## Benchmark limitations

Read benchmarks include percentile latencies and ten device zones. Results depend on caching, background I/O, transport, power management, temperature and filesystem state. The `compare-benchmarks` command requires the same device fingerprint and comparable run coverage. **No result is evidence of increased NAND program/erase endurance or repaired heads/platter damage.**

## Tests and packaging

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q driverepair_desktop
```

Hardware-free tests are not substitutes for controlled Windows, macOS and Linux device tests. There is no signed standalone installer or production-quality GUI yet.
