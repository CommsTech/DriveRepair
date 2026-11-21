# DriveRepair b37 media workflow qualification

## Implemented in code

- **All media:** safe read-only surface diagnostics, image rescue and integrity checks (subject to physical connection/driver limitations).
- **Windows NTFS/FAT/exFAT on HDD/SSD/NVMe/USB:** separately selected, operator-authorized, volume-bound CHKDSK `/f` path; backup and exact drive-letter confirmation remain required. Does not restore physically unreadable bytes or NAND cells.
- **Rotational HDD only:** journaled magnetic-region maintenance with existing read/verify/write authorization and identity/SMART gates. Never use it on SSD/NVMe or USB flash.
- **Serial-less boot USB stick on Windows:** may appear in *Create recovery USB* target list, but only becomes writable after Get-Disk independently proves a matching online non-boot/system USB whole disk and Windows locks permit access. Operator must select the exact disposable stick and explicitly accept permanent destruction. Other OS serial-less media remain excluded.
- **Manufacturer specs:** offline exact/family model lookup, with published source link. A workload TB/year or warranty/TBW figure is not a predicted drive service-hour limit. Unknown hour limit is displayed as unknown rather than asking the operator to guess.

## Required hardware tests (NOT COMPLETED by this source patch)

1. Windows x64 elevated application, two USB drives attached: the 7.61 GiB SMI USB stick with no serial and an unrelated patient SSD. Confirm only the deliberate SMI device is selected, correct disk index and capacity before erasing. Verify reconnect/renumber/size-swap aborts, that mounted/locked volumes behave correctly, and complete ISO readback. Use a **disposable** stick only.
2. Boot the resulting ISO on the HP laptop in normal and compatibility graphics. Confirm branded menu, graphical autologin, functional DriveRepair launcher, disk identification and zero writes during startup. Separately verify BIOS and UEFI virtual boot.
3. Windows external SSD and NVMe via USB dock: inspect the filesystem repair picker, choose a **disposable or backed-up** NTFS/FAT/exFAT volume, confirm the drive-letter and risk steps, perform CHKDSK only when approved, record before/after filesystem state and logs. Test unrelated disks and system disks are never chosen.
4. HDD via USB dock: collect `scripts/qa_smart_probe.py` output and sanitized Windows debug logs before any magnetic refresh. If identity/SMART/volume locks fail, no physical writes are authorized.
5. Unplug/reconnect scenarios: confirm read-only SMART refresh handles metadata dropout but a genuinely different disk is never accepted. Logs should clearly say whether the issue was a changed drive, missing drive, failed SMART command or blocked Windows raw access.

## Disclosure

Software can repair logical filesystem structures, move or rescue readable data, and sometimes help a controller remap weak HDD sectors. It cannot recreate unknown original bytes, repair failed NAND cells, or resurrect a failed SSD controller. A successful CHKDSK or surface scan does **not** establish healthy physical media.
