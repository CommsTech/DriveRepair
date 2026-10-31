# DriveRepair Open Issues Tracker

Updated: 2026-10-31

## Source
- Gitea: https://git.commsnet.org/commstech/DriveRepair/issues
- Audit: DriveRepair_Release_Competitive_Audit.md (SpinRite 6.1 competitive evaluation)

## Open issue inventory (65)

### Security / CI (close by pinning actions)
- #34, #35, #36, #37, #63, #64, #65 — mutable `actions-rs/toolchain@v1` / checkout tags in `.gitea/workflows/ci.yml`

### Tech-debt TODOs (close by implementing or removing TODO markers with real code)
- BIOS: #2,#3,#5,#6,#8,#10,#11,#38+ — disk_detection, disk_wrapper, enhanced, keyboard
- UEFI: #16 and related enhanced TODOs
- Disk: #21–#26, #29, #31, #39–#62 — ata/sata/nvme/usb stubs, detection

### Architecture “code islands” (close by wiring into lib/boot main paths)
- #1,#4,#7,#9,#12–#15,#17–#20,#27,#28,#30,#32 — disconnected boot/disk modules

### Summary rollups (close when child findings fixed)
- #33, #63, #64

## Audit P0 hard-stops (not filed as issues — must still fix)
1. Fail-closed stubs (no Ok(()) on unimplemented writes/TRIM/erase)
2. Read-only default + explicit destructive opt-in
3. Device identity + source≠dest validation
4. Boot-media exclusion
5. Durable recovery journal/mapfile (off-source)
6. Tests proving zero source writes in read-only modes
7. Stop privileged I/O crashing `cargo test` on Windows
