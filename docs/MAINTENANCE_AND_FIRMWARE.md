# DriveRepair 0.3.3b6 — Drive Maintenance & Firmware (experimental)

## Why these changes exist

A quick repair may refresh a few already-readable slow blocks without materially improving the health of the entire disk. A full scan of a failing USB drive can also stop on a rejected operating-system request rather than a genuine media defect. DriveRepair now offers separate read-only investigation, manufacturer firmware inventory, and drive-aware optimization advice.

These features are **not** physical platter repair, firmware flashing, a custom defragmenter, or proof that a drive is healthy. They do not replace a recovery image or a trusted independent backup.

## The read failure in the current Seagate lab

The supplied Full Scan log stopped at byte offset **77,561,069,568**, reading **4,194,304 bytes** (4 MiB), with `OSError errno=22`. The offset is aligned to 512, 4096, 1 MiB, and 4 MiB. On Windows, invalid-parameter errors can be caused by the I/O request, driver, or USB bridge; this is *not* proof of defective physical media. Do not reset, zero or rewrite this LBA based solely on error 22. Check the Windows `winerror`, SMART and USB path.

### Targeted investigation (read-only)

Run `driverepair-desktop list --json`, identify the selected whole disk and its `identity_hint`, and use:

```powershell
python -m driverepair_desktop probe-region --device windows:PhysicalDrive2 `
  --offset 77561069568 --length 4194304 --max-reads 32 `
  --confirm-identity YOUR_IDENTITY_HINT --ack-read-stress --json
```

Or choose **Diagnose / Rescue > Investigate a failed offset**. The tool does not write. It subdivides rejected read requests within a fixed budget and reports each attempt with its offset and result. If a 4 MiB read fails but smaller requests work, that may indicate a USB/driver request-size issue. Successful smaller reads still do **not** prove the original bits correct. If Windows returns a device I/O error or the transport loses connection, stop and investigate the dock, cable and power path rather than retrying indefinitely.

## Firmware identification — no flashing

```powershell
python -m driverepair_desktop firmware-info --device windows:PhysicalDrive2 --json
```

The report uses native Windows storage metadata where available and optionally `smartctl --info` to show the installed firmware revision. **Installed revision is not a statement that firmware is current.** `update_available` remains `NOT_CHECKED` until the manufacturer/OEM lookup for the **exact** drive model, real serial number and enclosure context is verified. USB bridges can mask or misreport identifying information. DriveRepair never downloads, flashes or stages firmware in this release. Firmware updates are potentially data-destructive: use the actual vendor instructions, tested power, and compatible hardware. See:

- Seagate official support: https://www.seagate.com/support/downloads/
- Microsoft drive firmware guidance: https://learn.microsoft.com/en-us/windows-server/storage/update-firmware

## Drive optimization (Windows only)

```powershell
python -m driverepair_desktop optimize-volume --device windows:PhysicalDrive2 --letter E --json
```

The default is **advisory only**. DriveRepair obtains the physical disk-to-volume mapping from Windows and refuses ambiguous, boot/system or mismatched volumes. It recommends:

- **HDD + supported filesystem:** OS-native `Optimize-Volume -Defrag` (only on demonstrably healthy media).
- **SSD + supported filesystem:** OS-native `Optimize-Volume -ReTrim` (only on demonstrably healthy media; retrim can complicate deleted-file recovery).
- **Unknown media, unsupported filesystem, SMART uncertainty, health warnings:** no write operation, analysis/recovery guidance only.

DriveRepair does not replace the OS optimizer or implement its own lower-level defragmenter. This avoids unproven file-move algorithms and filesystem corruption. A deliberate write operation is available to experts with all gates satisfied:

```powershell
python -m driverepair_desktop optimize-volume --device windows:PhysicalDrive2 `
  --letter E --confirm-identity YOUR_IDENTITY_HINT --execute `
  --ack-optimization-risk --json
```

The execution is refused unless fresh, positively mapped volume data reports **healthy** and independent SMART reports no selected fault evidence. Windows' coarse `HealthStatus` alone cannot authorize it. Do **not** defragment the slow/problematic Seagate described in these tests before understanding the read failure and protecting valuable data. Linux and macOS native optimization orchestration is not available yet.

Microsoft reference: https://learn.microsoft.com/powershell/module/storage/optimize-volume

## Remembered settings

DriveRepair now remembers the UI's non-sensitive **repair policy**, **journal choice** and **dashboard visibility** in a local per-user preferences file (Windows `%LOCALAPPDATA%\DriveRepair\preferences.json`, macOS Application Support, Linux XDG config). New installs default to the safer disk journal. Users may opt into volatile RAM storage, and that choice can be remembered for convenience. **Risk confirmations are NEVER remembered**: the user must acknowledge destructive writes and RAM crash-loss risk for every operation. No serial numbers, image paths, case data or personal files are saved in preferences. Invalid/corrupt preferences fall back to safe defaults.

## About “smoothing dimples”

The vendor's published explanations support magnetically refreshing readable recordings and firmware-driven reallocation of defective LBAs. They do not demonstrate a host-software method for physically smoothing dents, scratches or microscopic defects on platter surfaces. No such operation is implemented or claimed by DriveRepair. Full-surface pattern testing can destroy data and cannot restore mechanical health; it is intentionally not presented as physical resurfacing.

## Beta / release limits

Verified here: synthetic tests, no-device GUI integration, CLI help, package generation. Not validated here: Windows USB real-device error-22 probe, drive firmware revision retrieval through this particular USB bridge, native optimization on real volumes, bootable BIOS/UEFI runtime, physical write/refresh, SMART reliability or long-term failure prediction. These remain release gates. No automatic maintenance/defrag/firmware flashing is scheduled.
