# DriveRepair

**Diagnose storage problems, rescue readable data, and evaluate whether a drive is safe to reuse.** DriveRepair is a local-first desktop workstation and command-line toolkit for Windows, Linux and selected macOS workflows. It combines read-only diagnosis, image-based recovery, filesystem/file extraction, and *experimental, tightly controlled* HDD maintenance.

> **Release status:** `0.3.3b36` is a testing build, **not** a hardware-certified repair product. A read-only scan, a repaired filesystem, and an actual physical HDD rewrite are different outcomes. No software can restore bytes that the hardware can no longer return, or guarantee a failing drive's future lifespan.

**Drive models:** The bundled [offline model catalog](docs/DRIVE_MODEL_CATALOG.md) currently documents four vendor-backed model entries (three Seagate SMR models and one SanDisk SSD family). It guides scanning; it is not a comprehensive database or authorization to rewrite a disk.

The Qt workstation now selects an **automatic, bounded HDD investigation level** from available media and error evidence; it never uses a plan to bypass media-write safety. Expert CLI overrides remain for controlled laboratory work. Read [`docs/CAPACITY_AUTHENTICITY.md`](docs/CAPACITY_AUTHENTICITY.md) for the separate USB capacity-integrity test. See also `docs/STATISTICAL_SECTOR_RECOVERY_B18.md` for the level policies.

[Get started](#get-started) · [Choose a workflow](#choose-a-workflow) · [Recovery USB](#create-a-recovery-usb) · [Command line](#command-line-examples) · [Troubleshooting](#troubleshooting) · [Changelog](CHANGELOG.md) · [Support](https://github.com/sponsors/CommsTech)

## Repair a drive versus Restore data

**Repair drive** now preserves the selected HDD technique even if the media is
ineligible; the diagnostic next-step dialog no longer silently starts CHKDSK.
A button previously labeled "HDD method unavailable" despite a qualified HDD
now correctly says "Review guarded HDD maintenance". Physical writes are still
blocked without independently verified HDD identity, supported health evidence
(or separately qualified unknown-health native evidence), external-disk identity,
volume locks, and a durable separate-drive journal. The SMART probe now uses
smartmontools-documented `/dev/pdN` paths for Windows `PhysicalDriveN`; raw
Win32 I/O still uses its original physical-device path. smartctl exit status bit 0
means **invalid smartctl command line**, not evidence that the dock hides SMART.

**Repair drive** performs supported *on-device* operations. It no longer sends
SSD owners to imaging just because magnetic-disk rewriting does not apply.
Choose **Repair filesystem on selected drive (Windows)** for a supported
mounted NTFS, exFAT, or FAT volume. The repair screen discovers the eligible
volumes attached to the selected external disk asynchronously; operators choose
one from a bound list instead of typing a speculative drive letter. A RAW,
unmounted or unknown filesystem is NOT silently repaired or formatted.
The operator selects the applicable repair technique explicitly. An HDD
maintenance method will **not** be silently changed into CHKDSK; if the medium
is unsuitable, the UI explains that method is unavailable. CHKDSK is for
filesystem metadata only, never physical flash wear, unreadable sectors or
HDD surface regeneration. The command performs a second,
independent volume-to-PhysicalDrive check immediately before altering metadata.

Choose **Targeted HDD region repair** separately for a genuinely identified
rotational disk. The filesystem method invokes Windows CHKDSK `/f` on the
**original volume**; it can correct filesystem metadata but
**cannot repair NAND flash cells, an unreadable sector, worn parts, or lost
content**. It requires an existing backup, two explicit confirmations, a
fresh match between the chosen drive and the Windows volume, and an independent
non-system/external disk check. Locked, busy, unrecognized, or system volumes
fail closed rather than being forced offline or scheduled silently for reboot.

HDD physical-region maintenance uses DriveRepair's bounded, journaled rewrite
engine with separate media-type, identity, health, locking and readback checks.
It may re-write repeatably readable weak HDD regions; an unreadable region is
**not** reconstructed. The program cannot guarantee the drive's remaining life.

**Restore image storage:** The Restore workspace offers a default **space-saving
sparse image** option. Only all-zero chunks successfully read from the source
can remain unallocated on sparse-file capable destination storage. The image
retains its original logical disk size and exactly the observed bytes; an
independent `.rescue.json` journal distinguishes successfully read zeros from
unreadable/unprocessed areas. This is **not** filesystem-aware free-space
analysis or a compressed container, and copying the sparse image to another
filesystem may expand it. Disable this option for the simplest regular-file
workflow; neither mode proves forensic chain of custody.

**Recovery USB boot choices (next build, still unverified):** The rebuilt ISO
provides a **DriveRepair - Start recovery workstation** option (select this
first), **Compatibility graphics** (`nomodeset` for black-screen/frozen display
symptoms), and a **Troubleshooting text console** for diagnosis. The live XFCE
session is configured to autologin as `driverepair` and launch the DriveRepair
Qt workstation automatically. If a login prompt is shown, the expected Debian
Live fallback is **username `driverepair`, password `live`** (must be tested on
actual hardware). There is no hard-drive installer menu. The new build checks
that the ISO really contains the branded GRUB config, not just Debian's default
menu. Neither firmware compatibility nor Secure Boot is certified; see
[`docs/BOOT_RECOVERY.md`](docs/BOOT_RECOVERY.md) and
[`docs/DRIVEREPAIR_LIVE_START_HERE.txt`](docs/DRIVEREPAIR_LIVE_START_HERE.txt).

**Recovery USB creation:** Debian WSL builds now show an indeterminate live
progress window, keep a complete `DriveRepair-iso-build.log` in the chosen
output folder and reject build-hosts unable to create Linux device nodes
before downloading the full live image. A structurally checked ISO is still
not considered firmware-boot verified until tested on BIOS and UEFI.

**Diagnose** automatically requests a bounded read-only hardware-health probe
after a completed scan. When a USB adapter hides SMART, the observed scan
read errors are reported but **no drive life or reliability score is invented**.
Use **System readiness** to review local prerequisites and optionally approve
installation of supported Windows tools. No installer runs automatically.

**Restore data** is a **different workspace** for imaging, recovery and file
salvage. Recover files or use a restored image when the data matters more than
reuse of a potentially failing drive. These are distinct workflows and should
not be presented as interchangeable repairs.

## Cold storage integrity — check archived photos without another image

DriveRepair can now verify **ordinary files and folders** on an occasionally connected
USB hard drive or SSD. Open **Cold storage integrity** from the Qt sidebar. On the
first connection, choose the photo/archive folder and **Create new baseline**.
DriveRepair reads each regular file and saves a small, external **SHA-256 manifest**
(paths, sizes, hashes, and baseline timestamp). No full disk image is created and
**no source files are modified**. Store the manifest on a *different* physical disk
or in a trusted backup location — not in the protected folder. The manifest is
marked `UNATTESTED_BASELINE`: DriveRepair cannot know if an old photo was already
corrupt the first time it was scanned.

When you connect the drive again (for example every 3–9 months), choose the same
folder and **Verify against saved baseline**. The Qt flow compares file contents
against the earlier hashes, even if the drive letter has changed, and generates an
offline, navy-and-teal HTML report. It separates **unchanged, changed, missing,
new, and unreadable** files. Newly added pictures are *not* automatically called
corrupt. Review legitimate changes, **retain the old baseline**, then create a
new baseline under a different filename. Unlike a new baseline, old manifests
allow detection of historical changes.

**Important:** A matching checksum means the bits read now match the original
baseline; it is not a health guarantee, proof the baseline was correct, or a
backup. SHA-256 detects differences but cannot reconstruct lost photos. Keep at
least one independent copy of irreplaceable files, even if you do not retain a
full drive image. The archive check is read-only, but extra reads can stress an
already-failing drive; rescue critical data first if the drive is unstable.
Symbolic links and inaccessible files are not silently trusted.

CLI equivalent (works on Windows/Linux/macOS; drive letter can change):

```powershell
python -m driverepair_desktop archive-baseline --folder "E:\FamilyPhotos" --output "C:\ArchiveChecks\photos-2026-11.json" --json
python -m driverepair_desktop archive-verify --folder "F:\FamilyPhotos" --manifest "C:\ArchiveChecks\photos-2026-11.json" --report-html "C:\ArchiveChecks\photos-verify.html" --json
```

## What DriveRepair does

| Workspace | You can do | What it **does not** mean |
| --- | --- | --- |
| **Diagnose** | Read SMART/NVMe health where available, sample or scan drive regions, run an optional **write/restore USB capacity spot test** on a backed-up disposable drive, and export an offline HTML evidence report | A successful read is not proof that the bytes match the original file, or that the disk will remain reliable |
| **Restore data** | Copy readable sectors to a **new image on separate healthy storage**, record missing ranges, resume and retry bounded failed reads | A full-size image file is not proof that every byte was successfully recovered |
| **Repair drive** | On Windows, explicitly approved on-device NTFS/FAT/exFAT filesystem metadata repair; on eligible rotational HDDs, small journaled post-verified region rewrites | This cannot regenerate unreadable original bytes, fix mechanical damage, or make SSD/NVMe rewrites into "repairs" |
| **Analyze recovered images** | Recover select deleted files, carve recognized file formats, check compatible filesystems, work on a clone | File carving cannot reliably reconstruct every fragmented file or encrypted volume |
| **Create recovery USB** | Flash a separately built DriveRepair hybrid ISO to a **disposable USB drive** with full-image readback | This **erases the USB**. It does not image/repair a patient disk or establish that BIOS/UEFI boot has been tested |

**Designed for:** experienced technicians who need evidence, drive owners who want a guided recovery route, and developers testing recovery against synthetic or sacrificial disks. Raw-media repair is currently **engineering/beta only**.

### When USB SMART information is unavailable (Windows)

DriveRepair now automatically tries **two independent read-only identification paths**:
SMART/ATA SAT pass-through, followed by **Windows-native storage properties** and a bounded read-only **ATA IDENTIFY** attempt through compatible SAT USB bridges if SMART
fails or is not installed. The native query asks Windows for the disk descriptor, reported
seek penalty, TRIM capability, size, and serial suffix. This can sometimes identify an
external mechanical HDD behind a bridge that blocks SMART, but **USB adapters can hide or
misreport these fields**. Generic flash drives, SSDs, missing serials, conflicting sizes,
and unknown model families are not treated as safe candidates for magnetic-sector rewriting.

An HDD that passes this second identification path is **not declared healthy**. The guarded
beta can offer a separate, explicitly acknowledged **unknown-health lab repair** using a
small durable journal and verified rewrites on a disposable or already-backed-up drive.
The choice must still pass disk identity, exclusive lock, write-safety and batch checks;
no writes start automatically. Critical Windows health warnings still stop the candidate
path. If identification remains incomplete for **HDD media rewrites**, select **Restore data** and save a copy to a
separate healthy drive instead. A full SMART pass still supplies stronger health evidence.

Use **Hardware diagnostics → Inspect storage** for read-only low-level information. Seek
penalty alone is not evidence of HDD health and does not authorize patient writes.

**Windows recovery USB preparation:** the first-time Debian WSL prerequisite is now offered
as an explicitly approved setup action. It may need Administrator access, Internet, a
restart and first-run Debian setup. After building a genuine live ISO, independently test
its BIOS and UEFI boot; a successful USB byte-verify alone does not establish bootability.

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
python dist/DriveRepair-0.3.3b36-public-beta.pyz gui
```

Install optional `PySide6` in that Python environment if you want the new Qt workstation. The **public-beta** package blocks physical in-place writes. The separate **repair-beta** package may attempt the guided, HDD-only write workflow on sacrificial hardware with all safeguards enabled:

```bash
python scripts/build_desktop.py --repair-beta --no-wheel
python dist/DriveRepair-0.3.3b36-repair-beta.pyz qt-gui
```

For a CLI image-only example, use a source **regular file** and an unused output path:

```bash
python dist/DriveRepair-0.3.3b36-public-beta.pyz scan-image --image source.img --mode triage --json
python dist/DriveRepair-0.3.3b36-public-beta.pyz rescue-image --image source.img --output recovered.img --json
python dist/DriveRepair-0.3.3b36-public-beta.pyz rescue-status --output recovered.img --json
```

A repair-beta build is **not** a recommendation to write to a failing or valuable patient. See [hardware testing requirements](docs/USB_REPAIR_PREFLIGHT_B17.md) and [release gates](docs/RELEASE_STATUS.md).

## Using the desktop workspaces

### 1. Diagnose

Select the actual *source* disk; double-check its capacity and masked serial suffix. **Check HDD eligibility** in the Repair workspace is a read-only SMART/protocol probe, not a write authorization. If the bridge hides the real medium or serial, try a compatible SATA pass-through bridge or a controlled offline direct-SATA setup. Do not assume that a manufacturer model label by itself proves which physical disk is attached.

After a quick or full scan with recorded read failures, **Address scan errors…** can perform bounded, read-only rereads of **those saved offsets** without repeating the full-drive scan, or route directly to image rescue. Reread success is not a physical repair or integrity certificate.

The evidence map distinguishes **readable**, **slow**, **failed read requests**, and **untested** regions. Progress is the amount of the selected job completed; **measured read coverage** is the unique portion of the medium observed. These percentages can differ, especially on a quick sample. Failed read requests are not a count of bad sectors.

### Repair eligibility on external USB drives

In **HDD maintenance**, DriveRepair now shows one next action: **Enable SMART identification**, **Check drive SMART and identity**, **Rescue data to an image**, or **Review guarded repair**. If read-only SMART detection fails, the reason from the USB bridge is retained in the local expert log and the readiness guidance. An HDD model name or Windows HealthStatus alone cannot authorize physical writes; some USB bridges hide the underlying ATA rotational-media and SMART identity. If SMART evidence is sufficient, the actual engine still requires identity revalidation, a suitable durable journal, exclusive access and explicit write consent. If it is not sufficient, rescue remains available. See [Windows repair readiness checks](docs/REPAIR_READINESS_B23.md).

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

**No external drive appears in the Windows selector.** Press **Refresh** and allow Windows storage discovery to finish. The workstation now shows when discovery is slow or has timed out. Some USB/UASP enclosures identify as SCSI: DriveRepair only includes them after a separate read-only Windows USB-transport check. If Windows inventory commands fail entirely, a native read-only fallback may still list the disk, but it does not supply a trustworthy serial or authorize any physical writes. In an Administrator terminal, compare `python -m driverepair_desktop list --json` against Disk Management; see [Windows USB discovery and repair preflight](docs/WINDOWS_USB_DISCOVERY_B26.md).

**A known HDD appears but repair is blocked.** The physical-write path requires an independently verified external, online, non-system disk, device identity, eligible HDD-media/health policy, explicit consent, exclusive access, and a durable journal located on separate storage. In earlier revisions, the journal preflight incorrectly rejected **all CIM-discovered devices** even after a Get-Disk gate passed; b26 corrects that contradiction. A missing serial, unverified medium, mounted disk, or blocked USB adapter can still veto repair.

**The Flash button is grey.** Check all three wizard steps: select the USB **target**, type the exact `ERASE <device-id>` phrase, and **check the permanent-data-loss checkbox**. The status line explains the first missing step. Flashing is different from **Rescue data**, which saves the patient's readable bytes to a new image.

**Targeted HDD repair is disabled.** This is usually missing stable identity or SMART rotation/health evidence from the USB bridge. Use **Check HDD eligibility**. Install `smartmontools`, ensure the enclosure supports ATA SAT pass-through, or safely test offline via direct SATA; the software will not infer permission to write from a Seagate/SMR model label alone. Rescue to image remains available.

**Windows reports access denied / WinError 5.** The guarded writer now opens the raw physical disk with Win32 read/write sharing **after acquiring every accessible patient volume lock**, and keeps those locks until the raw handle is closed. This avoids a spurious conflict from `share=0`. It does **not** circumvent an actual lock denial. Close File Explorer/windows, antivirus scanners and file-indexing or backup jobs using the patient; verify Administrator privileges and review the exact `FSCTL_LOCK_VOLUME` / `FSCTL_DISMOUNT_VOLUME` error in the operator log. If a partition exposes no safe lockable volume handle, work offline rather than forcing an unmounted raw write. For an NTFS/FAT/exFAT filesystem correction, Windows CHKDSK manages its own volume locking; it cannot be made safe by borrowing the physical HDD writer's handle.

**A read stalls indefinitely.** The USB device/driver may have stopped responding. A cooperative Stop can only act after the current kernel request returns; an isolated read-only worker can be stopped, but the hardware may still need a safe disconnect. Avoid repeated stress on deteriorating media.

**Windows WSL builder reports `ERROR_ALREADY_EXISTS` or Debian path translation times out.** Do not repeat `wsl --install -d Debian` blindly. Run `wsl --list --verbose` to see whether Debian is already registered, launch the Debian app once to initialize it, reboot if Windows requests one, and only then retry the ISO builder. The b31 GUI no longer launches WSL just to translate `C:\...` staging paths; it assumes standard `/mnt/c/...` mounts and checks their availability when the Debian build actually starts. If your WSL automount location is customized, use a Debian VM or adjust the build environment rather than forcing a fallback path. A successful build still needs BIOS/UEFI boot testing.

**SMART results are unavailable.** Windows `HealthStatus` is only a coarse fallback and cannot authorize HDD repair. `smartctl` and a supporting bridge are needed for stronger evidence. Do not mistake an unavailable SMART report for a healthy drive.

## Architecture and contributions

The primary workstation is **Python / PySide6** with a Qt-only workstation. The CLI runs I/O in separate processes and has independent checks for physical device identity, risk acknowledgements and journals. A **Rust core** is present for selected image-based operations, but it is not yet a fully qualified native physical-disk backend. Documentation on the current limits is in [architecture.md](architecture.md), [security](SECURITY.md), and [contribution guidelines](CONTRIBUTING.md).

Automated tests operate on fixtures and synthetic images. They do **not** prove real Windows USB device locking, power-loss recovery, hardware remapping, SSD controller outcomes, or bootability. Report problems with anonymized logs and exact versions; do not publish full disk images, serial numbers or private recovered content.

### Testing and compact source packaging

Run the offline Python regression suite with `PYTHONPATH=desktop python -m pytest -q desktop/tests` (or `cd desktop && python -m unittest discover -s tests`). These tests use simulated data and cannot certify raw-device repair or bootable recovery media. The core Rust source must be checked separately with a compatible Rust toolchain; GUI workflows need a native PySide6/Windows test.

To produce a clean source ZIP without recursively bundling compiled Rust outputs, Python caches, or historical release ZIPs, use `python scripts/create_clean_source_archive.py --output /path/outside/repo/DriveRepair-Source.zip`. This operation does not delete your checkout, and the output is not a signed or hardware-qualified binary release. See [code audit notes](docs/CODE_AUDIT_B28.md) for tested paths and remaining verification gaps.

For release changes see [CHANGELOG.md](CHANGELOG.md). Older technical release discussions are preserved in [the README engineering-history archive](docs/README_ENGINEERING_HISTORY.md), not mixed into this getting-started guide.

**Support development:** [GitHub Sponsors — CommsTech](https://github.com/sponsors/CommsTech). Optional sponsorship does not grant access to recovered data or bypass any safety checks.

**License:** [MIT](LICENSE).

### Bootable recovery media (release requirement)

The Windows USB wizard is a **writer**, not an ISO operating-system builder. A small ISO that merely contains MBR/ISO9660 signatures is **not** a usable DriveRepair recovery OS. Releases must bundle a real Debian live-build ISO with a kernel, initramfs, `filesystem.squashfs`, and BIOS/UEFI boot entries. The GUI and physical flash command now reject images missing these components.

Build on Debian using `sudo bash scripts/build_live_iso.sh /path/to/empty-dir` and inspect with `bash scripts/check_live_iso.sh /path/to/DriveRepair-Live-amd64-UNVERIFIED.iso`. Boot-test that ISO in both BIOS and UEFI virtual machines, then on sacrificial USB media before claiming it works. A byte-for-byte USB readback proves copying, **not firmware boot**. On Windows, an ISO-hybrid USB can appear empty or lack a drive letter while still containing a Linux filesystem; only structural inspection and an actual boot establish functionality.

The desktop interface is Qt-only (PySide6). Its Specialist Tools dialog exposes image scanning, filesystem analysis, recovery and clone-only ext repair without the removed Tk UI. Disk writes remain guarded by the CLI and require drive identity, access, journal and explicit risk authorization.

### Offline CPU and RAM tests

The optional Debian recovery ISO build now includes Memtest86+ as a separate firmware boot-menu choice and a **Hardware Diagnostics (CPU / RAM)** desktop launcher for short, consent-based Linux tests using stress-ng. These tests do not repair disks or memory, and the ISO still requires BIOS/UEFI boot qualification before release.

**Repair & Restore** can start a read-only image of an SSD, flash device, or unqualified HDD without leaving the workspace. This saves recoverable data on **another healthy disk** and is not the same as restoring physical media reliability. When SMART is blocked, Linux sysfs can also provide limited, unverified identification hints; a USB adapter may supply misleading values.


### Repair versus Restore (desktop)

**Repair drive** performs on-device operations with distinct safety controls:

- **Windows logical filesystem repair (NTFS, exFAT, FAT):** an explicitly authorized `chkdsk X: /f` on a mounted, independently mapped *external* volume. This can correct filesystem metadata errors, **not** worn NAND, unreadable sectors, lost file content, or SSD endurance. It requires a prior backup, the selected drive's identity hint, matching Windows partition-to-disk evidence, and two approvals. It will refuse boot/system disks and unsupported/unknown volumes. A busy volume may refuse the operation rather than force a dismount.
- **Rotational HDD region maintenance:** journaled, bounded rewrites of repeatably readable HDD regions only when the stronger media, locking, and identity gates pass. No guarantee of improving disk life. Missing SMART does not grant permission to write.

**Restore data** is a separate workspace for imaging, copy-out recovery, and salvage. An SSD is never sent to Restore merely because an HDD-specific repair is inapplicable. Use Restore first for valuable or unstable media; on-device filesystem repair can sacrifice damaged file references.

On Windows, the guarded CLI can inspect the selected volume binding without writing:

```
python -m driverepair_desktop repair-windows-filesystem --device windows:PhysicalDriveN --letter E --confirm-identity THE_12_CHAR_HINT --json
```

Actual writes additionally require `--execute --ack-backed-up --ack-filesystem-write`. These flags are not a substitute for a backup or a successful verification afterward. The public read-only beta blocks execution.
