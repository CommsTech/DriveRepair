# DriveRepair

**Privacy-first disk diagnostics, image rescue, targeted file recovery, filesystem repair-on-clone, and experimental media maintenance.**

**Current build: 0.3.0b1 / engineering beta candidate — NOT approved for public hardware-repair use.**
The downloadable desktop program runs on Python 3.10+ with optional Tk GUI; a small, optional standalone Rust regular-image rescue core is being introduced. The original low-level Rust BIOS/UEFI boot code remains in `src/boot` but does not yet provide a validated system-recovery live environment.

**If a drive contains irreplaceable data:** stop repeated scans/in-place writes. Image to healthy storage with a validated recovery tool or consult a professional. A rolling media-refresh journal is **not a full backup**.

## Workflows

| Goal | Operation | Data at risk | Implementation |
|---|---|---|---|
| Identify a USB/external drive | `list` | No patient writes | Windows, Linux, macOS inventory (physical QA pending) |
| Find suspicious areas quickly | `scan --mode triage` | Read stress only | Deterministic stratified sample and bounded neighboring probes |
| Full surface readability | `scan --mode full --ack-risk` | Read stress only | Entire readable address space, no data correctness proof |
| Rescue data first | `rescue-image --multi-pass`, `rescue-external` | Source read-only; output written | Python imaging/resume; direct physical rescue currently Linux experimental |
| Recover selected deleted files | `list-deleted-fat32` → `undelete-fat32 --file-id ...` | Source image read-only | Conservative FAT32 contiguous candidate extraction |
| Recover across more filesystems | `list-deleted-tsk` → `recover-selected-tsk --file-id ...` | Source image read-only | Optional Sleuth Kit (`fls`, `icat`) binary; OS/filesystem support depends on installation |
| Salvage identifiable files | `carve-image`, `salvage-zip` | Source image read-only | PNG/JPEG and CRC-valid ZIP members (limited, no universal reconstruction) |
| Repair an ext filesystem | `check-ext-image`, `repair-ext-image` | Writes a NEW copy only | `e2fsck` required; original preserved |
| Monitor deterioration on schedule | `monitor-external` | SMART only by default; optional read stress | Private local trend history; never auto-refreshes |
| Capture forensic hashes | `evidence-image` | Source image read-only | SHA-256 + minimal privacy-preserving JSON report; not a chain-of-custody certification |
| Rejuvenate readable media in place | `refresh-image`, `refresh-external` | **CAN PERMANENTLY LOSE DATA** | Private hardware experiment; separate journal and explicit approvals |
| Sanitize before disposal | Not yet enabled | Intentional destruction | Implement media-appropriate validated methods; no unsupported DoD certification |
| Recover broken boot/system disk | Trustworthy live USB OS, run desktop CLI | Depends on workflow | Internal bootloader currently experimental/unverified |

## Install

```sh
cd desktop
python3 -m pip install .
python3 -m driverepair_desktop gui
# or: driverepair-gui
```

A portable `.pyz` is also produced by `python scripts/build_desktop.py`. The GUI requires Tk. No cloud, account, or telemetry is required. `smartctl`, `e2fsck`, and The Sleuth Kit are optional local programs for their corresponding functions.

### Quick sample scan

```sh
python3 -m driverepair_desktop list --json
python3 -m driverepair_desktop scan --device linux:/dev/sdX --mode triage --samples 128 --json
# Scan IDs are returned by `list`; do not guess disk names or paths.
```

A triage scan is only a **spot check**: even a clean result says nothing about unsampled sectors. If symptoms are severe, image before scanning repeatedly.

### Restore only selected deleted files

```sh
python3 -m driverepair_desktop list-deleted-fat32 --image safe-copy.img --json
python3 -m driverepair_desktop undelete-fat32 --image safe-copy.img \
  --output-dir new-recovered-folder --file-id CATALOG_ID --json
```

The GUI's **Recover deleted files** tab supports multi-selection and previews candidates before extraction. FAT32 uses reconstructed partial 8.3 names and assumes contiguous unallocated clusters. For NTFS/ext/exFAT and other TSK-supported volumes, install `fls` and `icat`, choose the Sleuth Kit backend and the partition's start offset **in sectors**, then select files. Even a metadata entry or a SHA-256 of the extracted file cannot prove recovered original content.

### Multipass image rescue

```sh
python3 -m driverepair_desktop rescue-image --image input.img \
  --output rescued.img --multi-pass --json
# If interrupted, repeat with --resume --multi-pass.
```

The first pass prioritizes readable regions, and the optional second pass tries missing regions in smaller pieces. The Python map is `rescued.img.rescue.json`; **unreadable areas are not silently certified as recovered**. The experimental Rust core uses its own incompatible `.rmap` map, so never interchange engines on the same job.

### Optional Rust recovery core

```sh
cargo test --manifest-path rust/recovery-core/Cargo.toml
cargo build --release --manifest-path rust/recovery-core/Cargo.toml
# Set DRIVEREPAIR_RUST_CORE to the compiled executable or place it on PATH.
python3 -m driverepair_desktop rescue-image --engine rust \
  --image input.img --output new-rust-rescue.img --json
```

The standalone Rust core currently handles **regular images only**, not raw physical disks. It uses bounded buffers, a forward pass and a reverse split-retry pass, plus an fsynced progress log. Windows Rust-core resume is disabled pending hard-link identity protections; use the Python engine for Windows resume. **Rust builds have not been run in the analysis environment**; the CI job will compile and test this crate after it is pushed. The existing legacy boot/disk driver code is not a verified native desktop engine. See [architecture](docs/ARCHITECTURE_CURRENT.md).

### Forensic / scheduled monitoring

```sh
python3 -m driverepair_desktop evidence-image --image safe-copy.img \
  --output new-manifest.json --case-ref CASE-001
python3 -m driverepair_desktop monitor-external --device linux:/dev/sdX \
  --expect-fingerprint FINGERPRINT12 --state /healthy-storage/drive-health.json --json
# Optional bounded read sampling: --triage --ack-read-stress
```

See [scheduled monitoring](docs/SCHEDULED_MONITORING.md) and [release and safety gates](docs/PUBLIC_BETA_GATES.md).

## Reliability and limits

- Source disk operations are read-only by default. Linux direct-disk rescue verifies separate destination physical ancestry; other operating systems support image workflows until equivalently safe raw-device isolation is proven.
- Device selection uses model, capacity, bus, location hints, masked serial and a short fingerprint. Revalidate immediately before any raw-device write. USB docks can obscure or change identifiers.
- In-place media refresh is **experimental, explicitly destructive**. Its disk journal is recommended; optional Linux RAM-file-system journaling requires power telemetry and explicit volatility acceptance. A UPS is not a disk backup, and cannot reverse physical wear.
- No claim of universal deleted-file restoration, physical-wear reversal, repaired damaged heads/platters, firmware repair, or government-certified sanitization is made.
- Read success is not proof of file correctness. Forensics requires suitable acquisition controls, provenance, evidence retention and independent review.
- This project does not transmit disk contents or telemetry to external services by default.
- Modern SSD sanitization cannot be reduced to seven sequential overwrites. See NIST SP 800-88 Revision 2 and organization-approved media-specific requirements.
- **Physical USB unplug, power-loss, and platform tests remain release blockers.** See [public beta gates](docs/PUBLIC_BETA_GATES.md).

## Documentation

- [Desktop installation and commands](desktop/README.md)
- [Current architecture and Rust migration](docs/ARCHITECTURE_CURRENT.md)
- [Guided system/boot recovery](docs/BOOT_RECOVERY.md)
- [Scheduled health checks](docs/SCHEDULED_MONITORING.md)
- [Competitor and laboratory benchmark protocol](docs/BENCHMARK_PROTOCOL.md)
- [Public beta readiness gates](docs/PUBLIC_BETA_GATES.md)
- [Project status](docs/PROJECT_STATUS.md)

## Build and tests

```sh
cd desktop
python3 -m unittest discover -s tests -v
cd ..
python3 scripts/build_desktop.py
# Rust tools are separately verified in CI when Cargo is available.
```

## License / privacy / contribution

MIT, see [LICENSE](LICENSE). No proprietary recovery algorithms or source code are bundled. Consult [SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before reporting test results or opening issues. Never publish patient serial numbers, file contents, authentication tokens, or recovery maps containing private paths without redaction.
