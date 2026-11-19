# DriveRepair

### 2026-11-19 partial-repair reporting and USB media safety

Recent Windows traces showed 248 failed **read requests** during a SanDisk SDSSDH3 USB session. A subsequent journaled refresh reported rewritten and readback bytes, but the final operation remained **partial with unresolved data**. The Qt workstation now displays that status and the actual independent postverification result; 100% of planned *steps* is not a healthy-drive certificate. The engine now refuses HDD-style physical writes unless the underlying rotational HDD medium is independently established. A SanDisk SDSSDH3 model label is an advisory SSD classification even when SMART is hidden behind a USB adapter, not a write permit. The read-only device-details UI preserves inventory facts when the optional Windows query fails. See `docs/PARTIAL_REPAIR_TRUTH_AND_USB_IDENTITY_20261119.md`.

**Save drives. Save the planet.** Drive diagnostics, image-first rescue, selective file extraction, clone-only filesystem repair and experimental original-media maintenance. Privacy-first and local by default.

> 🌍 **Our mission: Reduce e-waste by extending hardware life.** When a drive "dies," there's usually still data to rescue and life to restore. DriveRepair gives you the surgical tools to breathe new life into storage that's been written off.

> **Current source baseline: 0.3.3b14, with post-b14 beta hardening (unreleased). Not approved for unrestricted physical-drive repair.** The supplied source archive is an engineering build. Only the separately built `-public-beta.pyz` package has in-place image/physical-drive writes disabled by distribution policy. Do not distribute the engineering zipapp/wheel as a public safety-qualified release.

## E-Waste Mission

**Why DriveRepair exists:** The electronics industry treats storage devices as disposable. When a drive starts failing, the default response is "replace it." But most failing drives still contain recoverable data and can be restored to functional service.

DriveRepair exists to change that default. Our toolset is designed to:

- **Rescue data** from failing drives before they're discarded
- **Extend drive life** through surgical filesystem repair
- **Verify health** so you know when a drive is truly done
- **Clone before repair** to preserve the original state

Every drive saved is one less piece of e-waste. Every successful repair is a small victory for the planet.

## Create recovery USB — simplified workflow (unreleased)

The Qt sidebar now exposes **Create recovery USB** as the main action. If a local valid ISO-hybrid image is present in `images/` beside the application, in a known build output folder, or was selected previously, DriveRepair **preselects it**. You only select the sacrificial USB target and authorize its total erasure; written bytes are independently read back. A chosen ISO can be changed in the wizard. There is no online download or fabricated image.

**This source archive does not contain a built live ISO.** Without one, DriveRepair presents **Use existing ISO**, **Build ISO (Linux)**, and **Export build kit** instead of pretending a ZIP is flashable. To package a separately built, tested hybrid ISO into a Windows-ready distribution, use `python scripts/build_desktop.py --repair-beta --no-wheel --recovery-iso /path/to/DriveRepair-Live.iso`. The command stages `dist/images/DriveRepair-Live-amd64.iso` and its SHA-256 receipt beside the zipapp. The ISO still requires BIOS/UEFI and read-only hardware validation before calling it release-ready.

The sidebar also links to [GitHub Sponsors](https://github.com/sponsors/CommsTech) for optional support; sponsorship grants no special support guarantee. If a USB bridge hides its hardware serial, the GUI blocks *in-place repairs up front* rather than spending time scanning a disk that cannot safely pass the required physical-write identity gate. **Read-only diagnosis and rescue remain available.** See [USB creator and repair qualification](docs/ISO_FIRST_USB_UX_20261118.md).

## Workstation updates — November 18 (unreleased, requires native validation)

The updated Qt workstation offers a 64×12 full-device evidence map with **aggregated successful-read spans** (no more systematically undercounting throttled scan results), clearer current-phase vs. whole-job progress, visual condition indicators, multi-drive read-only rescue queueing, and three distinct boot-media actions: export a Debian live-ISO build kit, run the experimental ISO builder on a qualified Linux build host, or **Flash bootable USB** from an existing ISO-hybrid image. The USB action performs explicitly authorized full-disk destructive writing with byte-for-byte verification; it does **not** build the ISO, repair patient disks or prove hardware bootability. On trusted Linux live recovery, users can opt into read-only imaging of offline internal disks.

**Batch rescue is NOT batch repair.** Each source is revalidated, each output is a unique new image on healthy separate storage, and outcomes are logged. A Windows/USB kernel read can still stall; small I/O requests and worker supervision reduce but cannot eliminate this failure mode. The condition gauge is a **diagnostic evidence index**, never a warranty or remaining-life forecast. Exact-model vendor service-hour ratings may be entered manually; they are not auto-guessed from MTBF/AFR.

See [workstation, batch, reliability and boot-handoff details](docs/MULTIDRIVE_CONDITION_AND_LIVE_UI_20261118.md) for completed changes, limitations and Windows testing checklist. **The new capabilities are source-level, not a hardware-certified release.**

### 0.3.3b17: why an SMR Seagate can show “Repair ineligible” over USB

The ST1000LM048 model is listed as a **5,400 RPM SMR HDD** in Seagate's BarraCuda 2.5 datasheet. That classifies the *model* for read-only sequential-first imaging; it does **not** verify what a USB bridge currently exposes or whether source writes are safe. A separate SMART ATA Identify result with a valid rotation rate and health information is required for the guided HDD-rewrite workflow. This revision tries one bounded read-only `smartctl -d sat` fallback when the automatic USB SMART query lacks media type. If that fails, the repair action remains disabled and offers **Rescue to image instead**. To unlock a suitable HDD for testing, install smartmontools and use a bridge with SAT SMART pass-through or connect the patient through a safe offline SATA interface, then verify identity and available SMART evidence. The engine independently enforces all existing locks, journal, and confirmation gates.

A green map cell only means the bytes were readable during that request. An unreadable block is not reconstructed by HDD refresh; flash devices must never be treated like magnetic-sector repair targets. This is a bugfix and workflow update, **not** proof of revived drive lifetime or validation of Windows cancellation behavior.

## Start here — choose the safest workflow

| Your situation | Start with | What the result means |
|---|---|---|
| A drive is slow, unreadable or making errors | **Rescue data → Rescue selected external drive** to a NEW image on a separate healthy disk, then diagnose if the source can tolerate more reads | Source is not written; rescued data is not checksum-certified and bad sectors remain marked missing |
| You have a disk image and need another copy | **Rescue data → Recover from existing disk image** (new destination) | The rescue map records readable and missing regions; an apparent full-size sparse file is not proof of recovery |
| Files were deleted or a filesystem is damaged | Work from a **copy of the image** using FAT32/TSK/extraction or ext clone-repair tools | Results are limited, may be incomplete and do not guarantee original file contents |
| You want to refresh/repair the original image or physical drive in place | **Guarded `-repair-beta.pyz` build permits guided HDD-targeted writes; the image-first public build remains read-only** | Experimental. Requires SMART, separate durable journal, identity and exclusive-access checks, explicit consent and hardware validation |

### Installation and first run (Python 3.10+)

The desktop interface uses Python, optional PySide6 (Qt UI), and a Tk fallback. **No native Windows/macOS/Linux installer or certified boot image is provided.** With Python installed, build the public image-first zipapp from a vetted source checkout:

```sh
python scripts/build_desktop.py --public-beta --no-wheel
python dist/DriveRepair-0.3.3b17-public-beta.pyz gui
```

For a CLI image-only example, use a source **regular file** and an unused output path:

```sh
python dist/DriveRepair-0.3.3b17-public-beta.pyz scan-image --image source.img --mode triage --json
python dist/DriveRepair-0.3.3b17-public-beta.pyz rescue-image --image source.img --output recovered.img --json
python dist/DriveRepair-0.3.3b17-public-beta.pyz rescue-status --output recovered.img --json
```

For experimental **actual guided HDD repair** using a *separate*, explicitly restricted build, run:

```sh
python scripts/build_desktop.py --repair-beta --no-wheel
python dist/DriveRepair-0.3.3b17-repair-beta.pyz qt-gui
```

This build enables **guided `care-external` physical writes** (not unconditional write commands). It requires smartctl evidence of an HDD, separate disk-backed journal, fingerprint confirmation and exclusive locking; unknown/SSD/NVMe media are not rewrite targets. The GUI requests explicit data-loss and SMART-warning consent. This is for *sacrificial hardware testing*, not qualification for valuable media. See [repair-beta engineering and hardware handoff](docs/REPAIR_BETA_ENGINEERING_20261118.md).

Never use the patient disk as the recovery destination. If data is irreplaceable or hardware is rapidly failing, minimize further reads, prefer a validated imaging workflow, and consider a professional lab. No software can reliably reconstruct bytes never read or already overwritten.

### Flash a DriveRepair recovery USB (experimental; erases selected USB)

The **Qt GUI → Tools → Flash bootable USB** workflow now accepts an existing ISO-hybrid
file. The separate **Export ISO build kit** action only creates a ZIP; it is not
bootable media. On Debian, build an ISO first using the experimental live-build
recipe. On Windows, select an existing hybrid ISO to flash; building the ISO
still requires a prepared Debian environment.

The flasher lists only discovered USB physical disks with a serial, checks the
hybrid-ISO markers, requires typed `ERASE <device-id>` and a permanent-loss
acknowledgement, blocks OS system disks, and verifies the full written ISO by
readback. **All existing data and partitions on the selected USB are destroyed.**
The ISO must be on a DIFFERENT physical disk. Elevated Windows access and
exclusive volume locks (or root and unmounted media on Linux) are necessary.
The process may fail if a USB bridge or Windows volume holds a handle; do not
bypass OS locks. ISO file checksum verification against an independently
trusted release and real BIOS/UEFI boot testing remain separate tasks.

CLI (for advanced operators only; substitute live values from `driverepair list --json`):

```text
driverepair flash-usb --iso DriveRepair-Live-amd64-UNVERIFIED.iso \
    --device windows:PhysicalDriveN --confirm-identity <12-character-fingerprint> \
    --confirm-erase "ERASE windows:PhysicalDriveN" --ack-data-loss
```

The example is *not* a command to run literally and is destructive when
filled in with real values. The GUI is the recommended confirmation path.
See `docs/USB_FLASH_HARDWARE_QA_20261118.md`.

### Platform and capability status (not a certification)

| Capability | Windows | Linux | macOS |
|---|---|---|---|
| Regular image scanning and image-based recovery | Implemented in Python; synthetic tests | Implemented; local synthetic tests | Implemented in Python; native execution unverified here |
| Physical-drive inventory / read-only scan | Implementation present; USB/dock fault testing remains open | Implementation present; privileged device QA open | Discovery/read-only path present; native hardware QA open |
| Physical in-place sector writes | Engineering path and guarded HDD repair-beta available; image-first public beta blocked | Engineering path and guarded HDD repair-beta available; physical hardware unverified | Disabled pending volume-lock qualification |
| Standalone Rust core | Optional **regular-image rescue** backend only; OS parity not proven in this review | Optional regular-image rescue; Cargo build unavailable in this review | Optional source backend; OS parity not proven in this review |
| UEFI/BIOS/ISO boot environment | Experimental source/recipe, not qualified | Experimental source/recipe, not qualified | Not a validated recovery environment |

**Stop and recovery rules:** read-only Stop requests are honored at completed I/O boundaries; Windows/USB drivers can stall inside a kernel read. In-place operations never intentionally abort a transaction mid-write; a disk-backed journal holds only the active region, not a backup. Volatile RAM and hybrid modes cannot provide durable in-flight restoration. SMART HealthStatus lacking attributes is **UNKNOWN**, not a clean bill of health. A quick 10% sample is not whole-drive verification.

**Build and release authority:** `docs/RELEASE_STATUS.md` is the current capability/release gate. The historical sections below document previous engineering changes and are **not** statements that those operations are public-ready. For exact incremental changes after b13 see `CHANGELOG.md` → Unreleased. No speed or recovery superiority over SpinRite, DiskGenius or Acronis has been independently benchmarked.

## Workstation and rescue retry improvements (unreleased, November 18, 2026)

The optional Qt workstation provides a three-step workflow, keyboard-focus styling,
scrollable layout, highlighted goal selection, live patient-to-image rescue, and a
journal-backed rescue map/status that distinguishes bytes **saved** from source
**errors**. The default **Rescue data** operation now copies the selected external
drive to a **new** image on a different healthy physical disk; the existing
image-to-image operation remains separately available. Physical-drive rescue
requires an explicit risk confirmation and source identity checks in the CLI.

A targeted second pass can split unreadable requests to logical sectors, retry
a failing sector with at most 0–2 extra reads (`--retry-sector-attempts`, default
1), and require **two identical reads** before copying data newly recovered in
the second pass. Mismatched bytes remain unresolved in the journal instead of
being invented. This is an evidence-driven adaptive recovery method **not** a
trained neural model, a CRC/cryptographic source proof, or a guarantee of
successful restoration.

Engineering-only in-place repair planning now prioritizes repeatably readable
error areas and then high-latency weak areas when the operator's bounded
candidate count is exceeded. The existing journal, exclusive access, device
identity, preimage preservation, and read-back verification still gate every
write. Public image-first packages keep physical writes blocked.

See [engineering validation and handoff](docs/UI_RESCUE_ENGINE_HANDOFF_2026-11-18.md)
for tests, limitations, and manual release gates. **No real-drive repair or
neural-model success has been demonstrated by this code update.**

## Windows access and read-only Stop (0.3.3b13)

A partition without an accessible Windows volume handle blocks physical writes; an unpartitioned disk is not equivalent to an inaccessible partition. Guided scans retain findings on a pre-write lock failure. Read-only Qt scans now request cooperative cancellation, escalating only if the OS call remains unresponsive. See [Windows volume access and Stop](docs/WINDOWS_VOLUME_ACCESS_AND_STOP_0.3.3b13.md).

## Reliability and safe cancellation (0.3.3b12)

The Qt interface now separates current phase from estimated whole-job progress. Follow-up read errors consume actual retry attempts (including failures) and expose the currently investigated offset. Stop is cooperative during guided repair, never a mid-write abort. SMR and flash media use smaller bounded logical rewrite transactions; these are conservative, **not** factory-media rejuvenation. Full details and Windows testing instructions: [Bounded I/O and safe Stop](docs/BOUNDED_IO_AND_SAFE_STOP_0.3.3b12.md).

## Windows mounted-volume preparation and read-error boundaries (0.3.3b11)

The Qt Fix workflow can request a **temporary exclusive lock/dismount** of an external Windows volume with a drive letter. This is never done without the operation's explicit physical-write confirmation. Windows must establish exclusive access; in-use, unknown or system volumes remain off-limits. No forced dismount or permanent drive-letter removal is performed. Read-error investigations now look on both logical sides of failed requests with a strict additional-probe budget. These inspections are read-only and **do not establish physical damage or recover missing bytes**. See `docs/WINDOWS_VOLUME_PREPARATION_AND_ERROR_BOUNDARIES.md`. Windows USB repair remains hardware-unverified.

## Qt interface, honest coverage and reconnect work (0.3.3b10)

- Quick Repair and the Qt quick read-only check sample **at least 10% of the entire disk** via seeded, distributed locations—not a sequential 10% prefix. This can take many minutes on an HDD. New seeds permit successive investigations to cover different areas. Complete verification still requires a full scan.
- The new full-drive surface map shows **fractional coverage inside each fixed cell**. Tiny samples cannot paint a multi-GB cell entirely green. Failed-read markers report observations, not proven damaged sectors. Hover cells and use the new help icons for explanations.
- The Qt sampled-scan percentage bug is fixed (`100%` of planned work used to show `1%`). A time-left metric is back, distinct from recent transfer speed and job average.
- Qt now filters operations by Fix / Recover / Check goal and has **Drive details ⓘ** for read-only native OS data. Windows uses a separate `DeviceIoControl` inspector for read-only facts when PowerShell is slow, but that inspector **never authorizes writes**.
- Full **read-only** scans can be set to watch for USB reconnection and resume with a saved, offsets-only checkpoint and a freshly matched identity. RAM-only physical writes **cannot** be auto-resumed after loss of their active journal.
- Rust includes a small read-only firmware-vendor inspection interface. No vendor-specific unlocks, service-area writes, firmware flashing, or simulated AI reconstruction are enabled.

See [Qt/reconnect and vendor safety guide](docs/QT_UI_AND_HARDWARE_RELIABILITY_B10.md).

## Media-aware scanning and simplified workflows (0.3.3b8)

- **Quick Repair checks at least 10% of unique logical addresses**, using
  deterministic stratified-random positions across the *entire* selected disk.
  It is not a sub-minute check: a 1 TB disk requires reading at least 100 GB.
  Do not interpret that 10% sample as proof of health in the other 90%.
- **Full Repair uses bounded adaptive read sizes.** It checks a few early,
  sequential regions to select an initial read size, increases on good areas,
  and defers bad requests for budget-limited smaller reads. Windows I/O error
  1117 is an I/O error, not proof of physical platter damage.
- The exact manufacturer-listed `ST1000LM048` model has **SMR** recording.
  The software avoids interpreting USB as a media type and does not automatically
  extend rewrites to adjacent SMR logical regions (logical adjacency is not
  physical adjacency). A CMR-only advanced neighbor rewrite option requires
  explicit recording confirmation and independently repeated reads.
- The main Diagnose page hides most expert settings by default. Choose a disk,
  choose a goal, review storage, then click **Start job**. SMART installation
  is offered only when missing; nothing installs silently.
- Device identity must be independently verified before any patient write.
  Windows selected-disk inventory first tries a bounded `Get-Disk -Number`
  query instead of repeatedly enumerating every disk. If this hangs, writes
  remain blocked; read-only findings are still reported rather than discarded.
- Persistent anomaly hints are optional, metadata-only, and **never authorize writes**. RAM-only
  operations create no rescue journal and cannot resume after a crash.

See [media-aware scanning guide](docs/MEDIA_AWARE_SCANNING_0.3.3b8.md).

## Direct disk repair without a backup image (0.3.3b4)

Open **Diagnose / Rescue**, select the external drive by model, capacity and
fingerprint, then use **Quick repair** (sample and investigate suspicious
regions) or **Full repair** (read the full surface before selecting safe
refresh targets). The primary screen now offers **Volatile RAM only (no recovery image/journal)** or a disk-backed journal. No recovery image or copy is created during
in-place maintenance. For a whole-drive rewrite, use **In-place refresh** and
select `full`; this is significantly riskier, particularly on failing hardware.

- RAM-only holds the current sector-region and transaction state **in the
  running process**. It writes **no patient bytes to any backup image or
  journal files**. It also has **NO resume** after application crash/reboot;
  a partial write could be unrecoverable. A UPS does not fix this limitation.
- Windows and Linux have experimental in-place raw-device access with explicit
  device, risk and volatile-journal confirmation. The patient must be offline,
  unmounted and exclusive to this tool. macOS destructive hardware access is
  disabled pending safe volume locking and physical QA.
- **Recoverable error areas:** Quick/Full repair now perform bounded, read-only retries of known error regions, splitting a failed read into smaller aligned regions. Two identical recovered reads can qualify the region for a separately journaled rewrite after the writer again confirms the bytes. This does **not** establish their original correctness.
- **Still-unreadable or inconsistent data:** never overwritten automatically. Such regions remain UNKNOWN and produce a partial/not-success result. Separate destructive logical-sector reinitialization is NOT implemented or approved on physical hardware.
- **Hardware safeguards:** unstable USB transport/identity, critical SMART failure and unknown error offsets still block writes. A SMART warning requires an additional explicit risk acknowledgment. If repeated errors persist, stop and rescue/replace.
- Successful readback means the new recording matches the bytes just read;
  it **does not** prove original file correctness or restore hardware lifespan.
- The code has been tested on synthetic images only. **Do not run RAM-only
  repair on valuable, sole-copy data or a failing disk for public beta.**

See [direct repair and RAM-only operations](docs/NO_IMAGE_RAM_REPAIR.md).

## Guided repair policies and scan dashboard (0.3.3b5)

The external-drive page provides two tested repair policies:

- **Preserve**: refresh only slow, consistently readable regions outside known error chunks.
- **Balanced** (default): in addition, re-investigate known error chunks with a strict limit on read requests. A portion that returns identical bytes twice may be scheduled for the journaled writer, which checks again before writing and verifies after writing.

If the scan reaches the **16-read-error safety limit**, it stops further surface probing instead of repeatedly stressing the drive. **Balanced** guided repair can still investigate the known error offsets with bounded split/retry reads and refresh separately confirmed, readable regions. Any unscanned space is **unknown**, so the result is **partial** and not a whole-drive repair. A diagnostic scan remains strictly read-only.

A detected read error alone is **not** authority to erase, invent, or zero-fill unknown bytes. An unresolved sector remains unknown. A partial refresh returns a nonzero exit status and a warning, even if other regions were verified. A transport failure, critical SMART condition, missing error coordinates, or active filesystem is not a recoverable sector and remains a blocker. The separate `--ack-media-warning` and `--ack-unknown-health` flags acknowledge higher-risk operations; neither is a certification.

**GUI telemetry:** scan data cards display *actual bytes successfully read*, failed chunk count, measured throughput and ETA for the current operation (sampled Quick mode does not claim to read the entire surface). During refresh the cards show bytes rewritten and verified. The map uses explicit color swatches for unscanned, readable, in-progress, slow, investigation and failed/unknown regions. The map is an approximate visualization, not a complete bad-sector map or integrity certification.

For synthetic-image testing only:

```sh
python -m driverepair_desktop care-image --image synthetic.img \
  --journal /safe-storage/unique-guided-journal --mode quick \
  --repair-policy balanced --ack-risk --ack-destructive \
  --ack-no-backup --ack-data-loss-risk --json
```

**For public beta:** Do not perform unvalidated physical-drive in-place writes on valuable media. Windows USB-dock writes, unplug/replug, crashes, and stale power states still require sacrificial hardware tests.

## Graphical recovery dashboard (0.3.2b1)

Run `python3 -m driverepair_desktop gui` to launch the guided interface. Image,
external-device, and offline-system-drive rescue jobs now send **structured,
throttled rescue progress events** from the committed recovery map instead of
flooding PowerShell with raw offsets. The persistent dashboard shows a
progress bar, data saved, unreadable bytes, current/average throughput,
forward-pass ETA, an approximate activity map, destination free space and
incomplete-recovery warnings. Completed means the source reads were copied;
**it does not mean the original files are correct or verified**.

Use **Advanced details / engine log** to inspect technical output. Workflow
pages scroll on smaller screens; **Stop job** stays visible. Interrupted
image/external/system-drive rescues may be resumed with the corresponding
**Resume** action, provided the source and destination identity matches the
journal. Use **Retry gaps** only after the first pass is complete. Output
images, recovered files and maps are never automatically deleted by the UI.

For automation, rescue commands accept `--progress-jsonl --no-live-dashboard`.
JSONL events go to stderr; final result JSON remains on stdout. CLI terminal
output is now a compact single-line status on interactive terminals, or sparse
log milestones if redirected.

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
| Recover broken boot/system disk | Trusted Linux live USB → `list-all-linux`, `plan-system-recovery`, `rescue-system` | Source read-only; output separate | NEW offline Linux internal-disk rescue path; physical QA still required |

## Offline system-drive / one-internal-disk recovery

A broken OS drive cannot host its own rescue environment or a complete safety
copy. Boot a verified Linux live USB, provide separate USB/NAS storage, identify
the *unmounted* internal disk and choose the new **Recover OS drive** guided GUI
workflow (or `list-all-linux` → `plan-system-recovery` → `rescue-system`). Network
image targets can be mounted NFS/NFS4/CIFS/SMB/SSHFS shares; ambiguous local or
RAM destinations fail closed. Full details: [one-drive guide](docs/ONE_DRIVE_RECOVERY.md).

An **experimental** Debian BIOS/UEFI hybrid ISO *build recipe* is now provided,
but no built and boot-tested DriveRepair ISO is supplied. The original custom
firmware stubs are still not validated bootable recovery tools. Read
[boot instructions](docs/BOOT_RECOVERY.md) and
[final release gates](docs/FINAL_RELEASE_SECURITY_REVIEW.md).

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
- Scheduled monitoring raises an alert for nonzero media-fault counters on the
  **first sample**, rather than labeling a suspect drive an uneventful baseline.
  It never rewrites patient data autonomously. See
  [trust and preventive maintenance](docs/TRUSTED_PREVENTIVE_MAINTENANCE.md).
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


### Integrity and verified-copy restoration (0.3.3b1)

The desktop GUI now offers an **Integrity / bit errors** tab. It compares
SHA-256 chunk hashes against a previously captured baseline, distinguishes
unreadable data from mismatches, and can build a **new** corrected image from
verified reference chunks. Baselines created after corruption are not proof of
original correctness. See [Integrity Recovery](docs/INTEGRITY_RECOVERY.md).

This release does **not** introduce automatic on-disk bit correction.

### Reliable progress and Windows lab safety (0.3.3b2)

The image's **logical file size is not recovery progress**. Inspect the journal:

```sh
python -m driverepair_desktop rescue-status --output PATH/TO/recovery.img --json
```

The `clean_rescue_complete` field is authoritative for *completed OS reads*, not independent file-content integrity. Windows lab scripts no longer chain physical refresh automatically. See [rescue progress and lab safety](docs/RESCUE_PROGRESS_AND_LAB_SAFETY.md).

### Guided GUI reliability hotfix (0.3.3b4)

- Fixed all seven **Start here** workflow buttons. The old callbacks attempted
  to select nested Tk Canvas frames, which are not notebook-managed tabs.
- Hide unused recovery telemetry until a job starts; users can toggle the
  dashboard at any time. On small windows, scroll individual workflow pages.
- Portable Python zipapps now launch image rescues from their own archive.
- Unexpected interface callbacks produce visible error messages and log details.
- Verified actual button invocation, navigation, image rescue, and byte-exact
  output under a virtual Tk display; no physical disks were modified.
- Windows/macOS physical-drive workflows and Rust/boot components remain
  outside the scope of this GUI-only fix and are not release-certified.

For reproducing and verifying the Windows workflow-button fix, see [GUI acceptance tests](docs/GUI_QA.md).


### Drive maintenance, firmware inventory, and remembered preferences (0.3.3b6)

The Diagnose page now offers read-only **Firmware info**, **Optimize advice** and a bounded **Investigate a failed offset** workflow, avoiding another lengthy full scan to examine a known problem. User journal and repair policy choices are remembered locally, but destructive risk acknowledgments never are. Drive optimization uses Windows native tools only on qualified healthy volumes. Firmware reporting is inventory-only: **NO firmware downloads or flashing.** See [Maintenance and Firmware](docs/MAINTENANCE_AND_FIRMWARE.md) for exact commands and test limitations.

### Adaptive scanning and staged desktop jobs (0.3.3b8)

Full surface scans now adapt sector-aligned read request sizes, defer difficult areas for bounded smaller reads, and continue to healthy regions after isolated Windows I/O errors. A local **opt-in** anomaly history can prioritize known weak offsets on subsequent quick scans. The desktop GUI stages the job and asks the user to press **Start job** before I/O; it also checks optional health-tool prerequisites and offers a consent-based WinGet installer on Windows. See [Adaptive scanning and setup](docs/ADAPTIVE_SCANNING_AND_SETUP.md). This is not yet certified for physical-drive repair or public beta on valuable disks.

**RAM-only versus history:** RAM-only keeps sector data and transaction state in process RAM and never saves a recovery image or sector journal. An independently selected “Remember bad/slow locations” option may save a small, local, offsets-only diagnostic history on the host computer. It stores no sector bytes, file contents, or write authorization. Disable it when absolutely no diagnostic files are desired.

**Repeat Quick Repair:** Each physical-drive session uses a new recorded random sampling seed. The selected locations are stratified across the disk and processed in address order; a repeat run can inspect different areas. Saved anomaly locations (when enabled) are rechecked separately. A new seed does not establish full-disk integrity. Synthetic image tests retain deterministic sampling.

#### Rescue journal compatibility and image identity

New rescue journals bind progress to the destination file's filesystem identity
(device and file/inode number), not just its path and size. Resume and status
refuse legacy Python journals without that identity; Rust-core V1 maps are also
refused. Preserve those images and journals and start a new rescue to a new
output rather than attaching old progress to an unverified file. Filesystems
without a usable file identifier are not supported for Python rescue; Rust-core
resume is supported only on Unix. Filesystem identity is not a content hash:
in-place changes, identifier reuse, adversarial changes, and some network or
unusual filesystem behavior may not be detected. Keep the output and journal
on reliable storage and protect them from modification during and between runs.
