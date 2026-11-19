# Windows USB discovery and repair preflight — b26

## What changed

1. Windows CIM (`Win32_DiskDrive`) sometimes labels UASP-attached disks **SCSI**. DriveRepair now asks its separate, read-only native storage descriptor worker to verify **USB transport, index and disk length** before including those devices in the external inventory. A SCSI label alone never qualifies a disk as USB.
2. If CIM, WMIC and `Get-Disk` all fail or return no usable disks, DriveRepair queries a bounded range of native physical-disk handles in child processes. Native-only inventory is **read-only evidence** with no trusted serial. It cannot authorize in-place repair or unattended rescue requiring an authoritative serial.
3. Qt now times out a stuck inventory worker and displays failure diagnostics rather than an indefinite “Looking for drives” placeholder. Errors are also written to the optional local GUI debug log.
4. **Critical repair bug:** a later Windows journal preflight previously required the inventory source label `Get-Disk` even though the inventory was deliberately CIM-first. The preflight now runs an **independent `Get-Disk` external, online, non-boot/system gate** regardless of which method found the disk. This fixes a logic contradiction without skipping any gate.

## Windows hardware acceptance test (not executed in CI)

Run from an Administrator terminal with the app installed and a **sacrificial** USB HDD connected. First ensure the source disk contains no irreplaceable data.

```powershell
python -m driverepair_desktop list --json
python -m driverepair_desktop inspect-windows-disk --number 4 --json
```

Replace `4` with the disk number actually returned by inventory. Corroborate against Disk Management and `Get-Disk`. Do not use a guessed PhysicalDrive number. The second command is **read-only** and never grants write authority.

Open the Qt application. Confirm external disks are listed without waiting indefinitely. Test an ordinary USB flash drive, the SanDisk SSD, the Seagate HDD, and a UASP enclosure if available. Reconnect the dock, press Refresh and verify that any new PhysicalDrive number is checked again.

### Qualifying a sacrificial HDD repair

- The Seagate **model catalogue** alone must not authorize rewrites. Collect current device serial, HDD/media evidence and the independently checked Get-Disk state.
- If the bridge hides identity, keep the disk read-only; try a known compatible SAT enclosure or direct SATA rather than faking SMART evidence.
- Make a complete recovery image to separate, healthy storage; check the recovery journal for missing bytes.
- With an independently backed-up sacrificial disk only, verify consent, stable identity, Windows exclusive locks and a separately located durable journal. Attempt a *small* eligible HDD maintenance batch.
- Record original SHA-256 digests, post-write independent reads, health warnings and the final outcome; do not treat a completed write transaction as recovered unreadable data.
- Repeat after a USB reconnect and with an injected `Get-Disk` failure. The operation must fail closed if the disk is missing, boot/system, offline, has an identity mismatch, or cannot be locked.

### Important limitations

The code's Windows device handling has not been exercised on this machine. Native descriptor queries can fail due to driver permissions, and some USB docks hide the HDD or serial permanently. A correct Qt inventory does **not** establish successful physical repair. The public-beta build still prohibits patient writes; only the guarded experimental build can attempt approved HDD maintenance on suitable hardware.
