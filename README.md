# DriveRepair

**Diagnose storage problems, rescue readable data, and evaluate whether a drive is safe to reuse.** DriveRepair is a local-first desktop workstation and command-line toolkit for Windows, Linux and selected macOS workflows. It combines read-only diagnosis, image-based recovery, filesystem/file extraction, and *experimental, tightly controlled* HDD maintenance.

> **Release status:** `0.3.3b22` is a testing build, **not** a hardware-certified repair product. A read-only scan, a repaired filesystem, and an actual physical HDD rewrite are different outcomes. No software can restore bytes that the hardware can no longer return, or guarantee a failing drive's future lifespan.

The Qt workstation now selects an **automatic, bounded HDD investigation level** from available media and error evidence; it never uses a plan to bypass media-write safety. Expert CLI overrides remain for controlled laboratory work. Read [`docs/CAPACITY_AUTHENTICITY.md`](docs/CAPACITY_AUTHENTICITY.md) for the separate USB capacity-integrity test. See also `docs/STATISTICAL_SECTOR_RECOVERY_B18.md` for the level policies.

[Get started](#get-started) · [Choose a workflow](#choose-a-workflow) · [Recovery USB](#create-a-recovery-usb) · [Command line](#command-line-examples) · [Troubleshooting](#troubleshooting) · [Changelog](CHANGELOG.md) · [Support](https://github.com/sponsors/CommsTech)

## What DriveRepair does

| Workspace | You can do | What it **does not** mean |
| --- | --- | --- |
| **Diagnose** | Read SMART/NVMe health where available, sample or scan drive regions, run an optional **write/restore USB capacity spot test** on a backed-up disposable drive, and export an offline HTML evidence report | A successful read is not proof that the bytes match the original file, or that the disk will remain reliable |
| **Rescue data** | Copy readable sectors to a **new image on separate healthy storage**, record missing ranges, resume and retry bounded failed reads | A full-size image file is not proof that every byte was successfully recovered |
| **Targeted HDD repair** | On eligible, positively identified rotational HDDs: inspect weak but repeatably readable regions and perform small, journaled, post-verified rewrites | This cannot regenerate unreadable original bytes, fix mechanical damage, or make SSD/NVMe rewrites into "repairs" |
| **Analyze recovered images** | Recover select deleted files, carve recognized file formats, check compatible filesystems, work on a clone | File carving cannot reliably reconstruct every fragmented file or encrypted volume |
| **Create recovery USB** | Flash a separately built DriveRepair hybrid ISO to a **disposable USB drive** with full-image readback | This **erases the USB**. It does not image/repair a patient disk or establish that BIOS/UEFI boot has been tested |

**Designed for:** experienced technicians who need evidence, drive owners who want a guided recovery route, and developers testing recovery against synthetic or sacrificial disks. Raw-media repair is currently **engineering/beta only**.

### New: USB capacity authenticity and detailed reports

Use **Diagnose → Verify USB capacity** only on a **disposable, fully backed-up USB device**, never on a drive containing irreplaceable data. The test selects 144 distributed 4 KiB spots by default, saves each original region in a durable journal on **another physical drive**, temporarily writes random data, reads it back, and restores/independently verifies the original. A dishonest USB controller can overwrite unrelated positions, so even the write/restore design is **not data-safe** and a passing result **does not certify full capacity**. This is optional and not part of normal read-only diagnosis.

After a scan or test, select **View detailed report** to save a local, themed HTML report. The report separates claimed capacity, tested locations, read errors and observed latency; expert-level address evidence is expandable, not forced on new users. No external account or upload is required. See [capacity-test precautions](docs/CAPACITY_AUTHENTICITY.md).

## Choose a workflow

```text
Choose a source drive or existing image
              │
              ▼
       Identify / diagnose
              │
        Is data valuable?
          │            │
         YES           NO / image already secured
          │            │
          ▼            ▼
    Rescue to NEW     Review SMART and scan evidence
    image on another             │
    healthy disk                ▼
          │            Is this positively identified as
          │            a suitable rotational HDD?
          │                   │
          ▼               NO  │  YES
   Check saved image ◄────────┘   │
   and recovery journal           ▼
                         Optional guided HDD maintenance
                         with identity, consent, locks,
                         separate journal, readback checks
                                    │
                                    ▼
                           Verify results and reassess
                           whether replacement is needed
```

For **clicking/grinding disks, repeated disconnects, severe SMART failure, or irreplaceable data**, stop stressing the patient and consider a professional recovery lab. For SSDs, NVMe, SD cards and USB flash drives, prefer controller health information and image-first recovery, **not** generic HDD sector rewrites. An SMR drive needs a sequential-first approach; CMR and SMR identification must be supported by evidence, not only a name shown by a USB bridge.

## Get started

### Requirements

- **Python 3.10+** on Windows or Linux (some read-only tools also work on macOS).
- **PySide6** for the Qt workstation (`gui` and `qt-gui` both require it). The old Tk GUI is no longer shipped.
- **smartmontools / `smartctl`** provides disk-specific health and rotational-media identification. A packaged, integrity-checked Windows smartctl can live beside the `.pyz` in `tools/smartmontools/`; if absent, the Qt UI offers a consent-based Windows Package Manager setup. **The source ZIP and test build do not contain a verified smartctl executable**. Some USB bridges still block ATA/SAT passthrough.
- A **separate healthy physical drive** with space for a full recovery image and its journal. Do not save a rescue image to the patient disk.
- Appropriate OS permissions for raw-drive access. Windows may deny physical writes when a drive is mounted or held open. Do not bypass exclusive access checks.

### Start the desktop workstation from source

From a cloned or extracted DriveRepair repository:

```bash
cd desktop
python -m pip install -e ".[qt]"
python -m driverepair_desktop qt-gui
```

On Windows PowerShell, run these same commands using `py` if Python is installed as `py`. You may also use `python -m driverepair_desktop gui` to select the best available GUI, or `gui-legacy` as a deprecated compatibility alias (it opens Qt; Tk is not shipped).

**Quick first test:** Connect a *noncritical* external drive, launch **Diagnose**, verify model/capacity/serial suffix, run **Check disk health**, then choose **Quick surface check (read-only)**. A quick scan samples the disk and must not be described as a full-disk health certificate.

### Use a portable Python zipapp (no source installation)

```bash
python scripts/build_desktop.py --public-beta --no-wheel
python dist/DriveRepair-0.3.3b22-public-beta.pyz gui
```

Install optional `PySide6` in that Python environment if you want the new Qt workstation. The **public-beta** package blocks physical in-place writes. The separate **repair-beta** package may attempt the guided, HDD-only write workflow on sacrificial hardware with all safeguards enabled:

```bash
python scripts/build_desktop.py --repair-beta --no-wheel
python dist/DriveRepair-0.3.3b22-repair-beta.pyz qt-gui
```

For a CLI image-only example, use a source **regular file** and an unused output path:

```bash
python dist/DriveRepair-0.3.3b22-public-beta.pyz scan-image --image source.img --mode triage --json
python dist/DriveRepair-0.3.3b22-public-beta.pyz rescue-image --image source.img --output recovered.img --json
python dist/DriveRepair-0.3.3b22-public-beta.pyz rescue-status --output recovered.img --json
```

A repair-beta build is **not** a recommendation to write to a failing or valuable patient. See [hardware testing requirements](docs/USB_REPAIR_PREFLIGHT_B17.md) and [release gates](docs/RELEASE_STATUS.md).

## Using the desktop workspaces

### 1. Diagnose

Select the actual *source* disk; double-check its capacity and masked serial suffix. **Check HDD eligibility** in the Repair workspace is a read-only SMART/protocol probe, not a write authorization. If the bridge hides the real medium or serial, try a compatible SATA pass-through bridge or a controlled offline direct-SATA setup. Do not assume that a manufacturer model label by itself proves which physical disk is attached.

After a quick or full scan with recorded read failures, **Address scan errors…** can perform bounded, read-only rereads of **those saved offsets** without repeating the full-drive scan, or route directly to image rescue. Reread success is not a physical repair or integrity certificate.

The evidence map distinguishes **readable**, **slow**, **failed read requests**, and **untested** regions. Progress is the amount of the selected job completed; **measured read coverage** is the unique portion of the medium observed. These percentages can differ, especially on a quick sample. Failed read requests are not a count of bad sectors.

### 2. Rescue data (recommended first)

1. Choose **Rescue data → Rescue selected external drive to NEW image**.
2. Select a **new file on another healthy physical disk**, not on the patient. Keep its `.rescue.json` journal.
3. Read the success/missing-range report. A disconnected device can leave an incomplete image; reconnecting and resuming is a separate verified action.
4. Analyze copies of the recovered image. Compare hashes only against a pre-existing, independently trusted reference—not a checksum invented after the failure.

You can queue multiple sources for **sequential, read-only** rescues. The unattended queue is **not** an unattended physical-repair scheduler.

### 3. Targeted HDD repair (experimental)

1. Rescue important files or explicitly accept the risk of losing unreadable data.
2. Select a verified rotational HDD; check SMART, serial/identity, mount state and transport stability.
3. Use **Check HDD eligibility** if the interface lacks SMART evidence. The UI cannot approve a job that the authoritative engine rejects.
4. Review the rewrite warning, type the exact device fingerprint and use a **durable journal on separate healthy storage**.
5. Observe the journaled transactions and fresh readback verification. Review unresolved reads and SMART changes afterward. **Completing every planned rewrite is not equivalent to fixing the disk.**

DriveRepair intentionally refuses HDD-style rewrites on SSD, NVMe, removable flash and unverified USB media. Such devices can still be scanned and rescued read-only. If the HDD drive remains ineligible even after SMART probing, the safe supported workflow is **Rescue to image instead**.

## Create a recovery USB

This is **boot-media creation**, *not* a way to back up a patient drive.

1. Obtain a DriveRepair hybrid live ISO that has been separately built and qualified. When a local `DriveRepair-Live-amd64.iso` is available beside the application or from a prior selection, the wizard preselects it.
2. Open **Create recovery USB**, and select a **disposable USB stick**. All existing partitions and data on that stick will be destroyed.
3. Type exactly the displayed `ERASE <device-id>` confirmation **and check the separate permanent-data-loss acknowledgement box**. Until all three requirements are complete, the Flash button remains disabled and the wizard tells you what is missing.
4. Review the final OS-level confirmation, then flash. The program rereads the written image and checks its bytes. A readback match is **not** proof that the media boots.

**Important:** The repository includes a Debian live-ISO build recipe, **not a qualified, preinstalled universal recovery OS**. On Windows, select **Create recovery USB → Build recovery ISO on this computer**. DriveRepair uses an existing **Debian WSL** distribution, copies its sources into WSL's Linux filesystem, installs the Debian build tools after your explicit approval, and builds an ISO; it **does not install WSL automatically**. If Debian WSL is absent, install it once using `wsl --install -d Debian` in an Administrator terminal and reboot if required. The ISO is not ready for distribution until independently boot-tested. An advanced operator can also run `scripts/build_live_iso.sh` on a prepared Debian Linux host; see [boot recovery documentation](docs/BOOT_RECOVERY.md). A release maintainer may package a built ISO alongside the desktop app:

```bash
python scripts/build_desktop.py --repair-beta --no-wheel --recovery-iso /path/to/DriveRepair-Live-amd64.iso
```

The ISO must still pass independent BIOS/UEFI and device-access tests. The GUI will not invent or silently download an ISO. The Windows WSL build downloads packages from configured Debian repositories only with operator consent; it does not flash a USB until separately authorized. Do **not** select your patient drive as the USB flash target.

## Command-line examples

Use `python -m driverepair_desktop <command> --help` for the full set of flags. From the repository root, run with `PYTHONPATH=desktop` on Linux/macOS, or execute from `desktop/` after installation. The examples below assume it is installed.

```bash
# Discover safe-to-list external whole-disk identities
python -m driverepair_desktop list --json

# Read-only SMART/NVMe health (optional smartctl; no raw rewrites)
python -m driverepair_desktop health --device 'DEVICE_ID' --json

# Rescue an external drive to a NEW image elsewhere (reads may still stress a failing drive)
python -m driverepair_desktop rescue-external --device 'DEVICE_ID' --output 'new-recovery.img' --ack-risk --json

# Examine the journal; image file size is NOT recovery progress
python -m driverepair_desktop rescue-status --output 'new-recovery.img' --json

# Image-only diagnosis and recovery; the original image is not overwritten
python -m driverepair_desktop scan-image --image 'source.img' --mode triage --json
python -m driverepair_desktop rescue-image --image 'source.img' --output 'new-copy.img' --multi-pass --json
```

For destructive operations, use the GUI's explicit review and *do not copy arbitrary CLI flags from the internet*. The CLI independently enforces drive identities, permissions, journal requirements, and write policy.

## Understanding the results

| Reported outcome | Interpretation |
| --- | --- |
| **Completed scan** | All planned reads were attempted; a quick sample may leave most of the disk untested |
| **Completed with read errors** | Some read requests failed; this is not an exact bad-sector or corrupt-file count |
| **Rescue incomplete** | Some ranges are missing or unverified; retain the image and recovery journal |
| **Partial HDD maintenance** | Some eligible regions may have been rewritten and verified, but other error evidence remains |
| **Repair not eligible** | A required proof of medium, SMART state, identity, exclusive access or journal is missing |
| **I/O stalled** | An OS storage/USB driver has not returned an I/O result; even Stop cannot always interrupt kernel I/O |

Drive condition scores are **evidence-based diagnostics**, not exact remaining-life predictions or manufacturer warranty equivalents. Unknown SMART is **unknown**, not healthy. After repair or rescue, verify data against an independent trusted copy and consider replacing unreliable media.

## Troubleshooting

**The Flash button is grey.** Check all three wizard steps: select the USB **target**, type the exact `ERASE <device-id>` phrase, and **check the permanent-data-loss checkbox**. The status line explains the first missing step. Flashing is different from **Rescue data**, which saves the patient's readable bytes to a new image.

**Targeted HDD repair is disabled.** This is usually missing stable identity or SMART rotation/health evidence from the USB bridge. Use **Check HDD eligibility**. Install `smartmontools`, ensure the enclosure supports ATA SAT pass-through, or safely test offline via direct SATA; the software will not infer permission to write from a Seagate/SMR model label alone. Rescue to image remains available.

**Windows reports access denied / WinError 5.** Close programs using the disk, verify Administrator privileges and that Windows can grant exclusive access. DriveRepair must not override locks, active volumes or OS-level device protection.

**A read stalls indefinitely.** The USB device/driver may have stopped responding. A cooperative Stop can only act after the current kernel request returns; an isolated read-only worker can be stopped, but the hardware may still need a safe disconnect. Avoid repeated stress on deteriorating media.

**SMART results are unavailable.** Windows `HealthStatus` is only a coarse fallback and cannot authorize HDD repair. `smartctl` and a supporting bridge are needed for stronger evidence. Do not mistake an unavailable SMART report for a healthy drive.

## Architecture and contributions

The primary workstation is **Python / PySide6** with a Qt-only workstation. The CLI runs I/O in separate processes and has independent checks for physical device identity, risk acknowledgements and journals. A **Rust core** is present for selected image-based operations, but it is not yet a fully qualified native physical-disk backend. Documentation on the current limits is in [architecture.md](architecture.md), [security](SECURITY.md), and [contribution guidelines](CONTRIBUTING.md).

Automated tests operate on fixtures and synthetic images. They do **not** prove real Windows USB device locking, power-loss recovery, hardware remapping, SSD controller outcomes, or bootability. Report problems with anonymized logs and exact versions; do not publish full disk images, serial numbers or private recovered content.

For release changes see [CHANGELOG.md](CHANGELOG.md). Older technical release discussions are preserved in [the README engineering-history archive](docs/README_ENGINEERING_HISTORY.md), not mixed into this getting-started guide.

**Support development:** [GitHub Sponsors — CommsTech](https://github.com/sponsors/CommsTech). Optional sponsorship does not grant access to recovered data or bypass any safety checks.

**License:** [MIT](LICENSE).

### Bootable recovery media (release requirement)

The Windows USB wizard is a **writer**, not an ISO operating-system builder. A small ISO that merely contains MBR/ISO9660 signatures is **not** a usable DriveRepair recovery OS. Releases must bundle a real Debian live-build ISO with a kernel, initramfs, `filesystem.squashfs`, and BIOS/UEFI boot entries. The GUI and physical flash command now reject images missing these components.

Build on Debian using `sudo bash scripts/build_live_iso.sh /path/to/empty-dir` and inspect with `bash scripts/check_live_iso.sh /path/to/DriveRepair-Live-amd64-UNVERIFIED.iso`. Boot-test that ISO in both BIOS and UEFI virtual machines, then on sacrificial USB media before claiming it works. A byte-for-byte USB readback proves copying, **not firmware boot**. On Windows, an ISO-hybrid USB can appear empty or lack a drive letter while still containing a Linux filesystem; only structural inspection and an actual boot establish functionality.

The desktop interface is Qt-only (PySide6). Its Specialist Tools dialog exposes image scanning, filesystem analysis, recovery and clone-only ext repair without the removed Tk UI. Disk writes remain guarded by the CLI and require drive identity, access, journal and explicit risk authorization.
