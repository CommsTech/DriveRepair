# DriveRepair Qt workstation and interrupted-scan recovery (0.3.3b9)

## What changed

The optional PySide6 workstation is a simpler interface to the **existing** recovery CLI, not a second disk engine. From the launcher select **Fix my drive**, **Recover files**, or **Check drive**; then explicitly press **Start selected job**. Drives are identified by model, capacity, bus, masked serial and a short fingerprint. I/O runs in a child process, and the interface can remain responsive even when Windows device enumeration hangs. The recovery map is a coarse read-activity summary, **not** physical platter topology and not a certificate of bit correctness.

To install:

```powershell
cd desktop
python -m pip install -e ".[qt]"
python -m driverepair_desktop qt-gui
```

For portable `.pyz`, install PySide6 into the same Python interpreter first, then run `python DriveRepair-0.3.3b9.pyz gui`. Without PySide6, `gui` prints a warning and launches the existing Tk interface. All existing specialist functionality remains available with `gui-legacy`.

Qt/PySide6 is subject to LGPLv3/GPL/commercial licensing. Review distribution and library-replacement obligations before shipping a bundled installer. No new network APIs or cloud services are used.

### Recovery speed metrics

**Recent speed** is a rolling five-second throughput sample based on successive committed/read byte counters. **Job average** is total progress divided by elapsed time. Neither speed represents an instant guarantee of future throughput; retries and disconnects can reduce both. When two samples are unavailable, recent speed is unknown instead of mislabeled as an average. The legacy Tk UI has also stopped calling the whole-job average “current speed.”

### USB removal and scan resumption

For an **adaptive full read-only scan**, DriveRepair saves a small local checkpoint to `~/.driverepair/scan-checkpoints/` by default. It contains a hashed media identity (model, reported serial, size, sector size, bus), current byte position, read-error offsets, and limited slow/unknown range metadata. It contains **no source sector bytes**. Files are local and are never uploaded or automatically deleted. You can override its destination with `--scan-checkpoint PATH`.

```powershell
# Scan. A disconnection will halt the job and preserve a checkpoint.
python -m driverepair_desktop scan --device windows:PhysicalDrive2 --mode full --ack-risk --json

# AFTER the same USB disk is physically reconnected and discoverable again:
python -m driverepair_desktop scan --device windows:PhysicalDrive2 --mode full --ack-risk --resume-scan --json
```

The application **never automatically resumes a physical write** after disconnection. It must re-enumerate and verify the current disk identity; if Windows `Get-Disk` freezes or returns a changed identity, it fails closed. A changed `PhysicalDrive` number alone need not invalidate the **read-only** scan checkpoint, but a missing/ambiguous reported media serial, changed USB bridge identity or duplicate bridge serial can prevent trustworthy resumption. These stable checkpoint keys never authorize writes; physical writes still use stricter path-specific checks. Previously failed ranges remain unresolved until re-examined; a checkpoint alone does not prove they were read. Already visited read-only areas need not be scanned from byte zero. USB recovery is manually triggered, not automatic hot-plug resumption; automatic detection and validation are still unqualified on Windows hardware.

For a **guided Full Repair** with `--journal-backend memory`, **no scan checkpoint is saved by default**. This preserves the promise of no saved files in RAM-only mode. If you explicitly accept a small offsets-only metadata file (not a sector journal), add `--scan-checkpoint auto` and later `--resume-scan` with the same saved metadata. This still cannot resume a lost *RAM write transaction*. The Qt interface asks before enabling that optional checkpoint. A disk-backed recovery journal is preferable if valuable data is involved.

The scanning and checkpoint paths are **read-only against the source**. The user must separately authorize every in-place repair workflow. The program cannot guarantee that a drive with a broken controller/USB bridge will reopen or survive another scan.

## Engineering decisions on advanced proposals

**Firmware layer:** SCSI generic and NVMe admin passthrough are mediated by OS and controller drivers; they do not magically bypass a failed controller. Vendor service-area commands, translator edits, SMR mapping repairs, forced bootloader modes and raw NAND reads are **model- and firmware-specific**, can permanently brick media, and are not verified here. This release adds no arbitrary vendor-command console, unlock sequence, or firmware write. Existing read-only firmware inventory remains. Only documented, authenticated vendor tools and a bench-qualified device matrix should ever be used for firmware service.

**AI-assisted recovery:** learned fragment classifiers can help prioritize *candidates* on forensic copies. Classification confidence is not the original bytes or a verified file reconstruction. Untrained CNN/Transformer samples, a generative GAN patch, and arbitrary gap-stitching must not be marketed as reliable recovery. This release does not add unvalidated model weights, secretly fill unreadable sectors with synthetic data, or alter original evidence. A future optional lab mode could propose files on a separate copy, track exact provenance, validate against known file structure, and clearly label synthesized bytes as synthetic.

**IPC:** Continue using the existing progress JSONL between the CLI and Qt. Raw disk contents remain inside the recovery engine; no shared-memory daemon, extra controller, or device-specific service is necessary to paint the GUI. Progress is throttled, so the UI does not run at the disk's I/O event rate.

**Stop controls:** Read-only jobs can terminate. In-place writes cannot be guaranteed safe if forcibly stopped in the middle of a write; the Qt UI refuses to call such a termination a safe stop. Cooperative transaction-boundary cancellation must be implemented and hardware-qualified before replacing that behavior.

## Release validation and remaining gaps

- Synthetic read-only fault-injection: Windows `winerror=433` is classified as device loss, no writes are issued, a checkpoint is stored, and a fresh same-identity reader resumes at the last safe offset.
- Test checkpoint identity/geometry mismatch, invalid offsets, and rolling recent throughput.
- Existing Python tests remain part of CI. Rust compilation and boot image qualification still require their native toolchains.
- **Qt runtime integration needs a Windows/macOS/Linux PySide6 install.** This build environment does not include PySide6, so the Qt UI is source/compile checked here, *not* represented as a completed GUI clickthrough.
- **Windows USB unplug/replug and disk identity rechecks need physical hardware testing.** A simulated disconnect does not prove that a real USB bridge, OS cache, or disk firmware recovers reliably.
- Physical recovery and firmware modifications remain experimental or disabled. No competitive superiority or recovery-success guarantees are asserted.
