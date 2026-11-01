# Data integrity, changed bits and selective recovery

**Status: experimental image-only integrity tools. No physical-disk write support.**

## What a successful read means

A successful raw disk read means that the operating system/device returned bytes. It does **not** prove that the bytes match the data originally written, or that the files are semantically intact. Most ATA/NVMe devices perform their own ECC internally, but corrected/uncorrectable media errors, controller/transport failure, and silent corruption are not interchangeable. Repeated identical reads are not a substitute for previously trusted checksums.

DriveRepair distinguishes:

| Result | Meaning |
|---|---|
| Readable | Device responded with bytes; correctness not established |
| Hash matched | Bytes match an external pre-existing baseline for this chunk |
| Hash mismatched | Bytes differ from baseline, but that alone doesn't locate physical cause |
| Unknown | The rescue journal reports unreadable/unvisited bytes, or read returned an error |
| Verified restored copy | A **new output image** matches all expected reference hashes after suspect chunks were replaced with verified reference bytes |

Only compare copies that represent the **same immutable point-in-time snapshot**. A manifest from last month applied to a live-updated drive could interpret perfectly legitimate file changes as corruption. Do not "restore" an older snapshot over newer data without intending that rollback.

Do not call a blank or sparsely allocated region recovered. An image created from an already-corrupt disk can have a perfectly matching **newly created** manifest and still contain corruption. For trustworthy detection, preserve hashes from before a failure or obtain them from a separately verified known-good copy, backup, signed vendor distribution, or filesystem metadata with verified provenance. These JSON manifests are NOT authenticated or cryptographically signed; protect them from modification and keep an independent copy.

## Guided commands

From `desktop` with Python 3.10+:

```sh
# On a known-good image, BEFORE corruption is suspected; save outside patient disk.
python -m driverepair_desktop integrity-baseline \
  --image known-good.img --output known-good.sha256chunks.json \
  --chunk-mib 16 --json

# Later, find which chunks in another image differ from the saved baseline.
python -m driverepair_desktop integrity-audit \
  --image suspect.img --manifest known-good.sha256chunks.json --json

# Optional: restore only changed chunks from an independent, checksum-matching
# known-good image into a NEW output image. Original images remain untouched.
python -m driverepair_desktop integrity-restore-copy \
  --image suspect.img --reference trusted-copy.img \
  --manifest known-good.sha256chunks.json \
  --ack-same-snapshot --output corrected-new.img --json

# Optional: on a sampled diagnostic scan, double-read *suspicious* chunks.
# May stress a failing device; divergent reads mean UNKNOWN correct bits.
python -m driverepair_desktop scan-image --image suspect.img \
  --mode triage --compare-suspects --json
```

GUI: **Integrity / bit errors** tab. `Create baseline` is an *unattested* manifest and is not itself proof of correctness. `Check for changed chunks` shows offsets and counts. `Restore proven chunks` creates a **new** full-size image, potentially requiring space for another full image. On compatible Linux copy-on-write filesystems, the tool attempts a reflink clone to minimize data duplication and only writes verified changed chunks; it falls back to a full streaming copy if unsupported. Output is read back for hash comparison. Protect the original and do not use the experimental feature directly on valuable physical media.

## Performance / strategy

- **First pass**: sequential rescue copies accessible bytes rapidly, minimizing time spent on failing areas.
- **Missing reads**: retry only journaled missing ranges, with smaller reads and an explicit failure budget, rather than rescanning the entire disk.
- **Suspected slow regions**: sampled triage probes nearby chunks; optional repeated-suspect reads detect instability, not the true value.
- **With a known-good checksum baseline**: hash every image chunk once, report exact **chunk ranges**, and read the independent recovery source **only for mismatched chunks**. Smaller chunk sizes narrow the targeted recovery area but increase manifest size and metadata processing.
- **Without trustworthy reference data**: DriveRepair cannot identify or safely correct an arbitrary silent bit flip. Prefer recoverable backups, filesystems with checksums and redundant copies (ZFS/Btrfs), parity recovery archives, vendor package signatures, and application-aware checks.

Read/write performance benefits must be measured on equivalent devices and error maps, with **verified correct bytes, source I/O, latency, failure rates, recovered coverage, and destination writes**. A fast scan that never sampled the bad block cannot establish superiority over a full scan.

## Constraints before beta

- Current desktop recovery remains primarily **Python** with a separate experimental Rust image core. The new integrity functionality is Python, not yet in Rust.
- No source-drive writes, automatic bit fixing, firmware repairs or live filesystem repair are introduced by this release.
- Incomplete rescue journals produce **UNKNOWN** chunks, not corruption findings. The image repair command declines those inputs rather than presenting a complete result.
- No end-to-end signed reference-manifest trust chain or per-file filesystem block mapping yet.
- Hardware disk failure may make extra reads unsafe. Users should choose rescue-first and work on images whenever possible.
- No BIOS/UEFI boot validation or Windows/macOS hardware qualification is implied.

### Documentation references

- [OpenZFS checksums](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Data%20Storage/Checksums.html)
- [OpenZFS scrub and repair](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Operations/Scrub%20and%20Resilver.html)
- [Btrfs scrub](https://btrfs.readthedocs.io/en/latest/Scrub.html)
- [GNU ddrescue manual](https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html)
