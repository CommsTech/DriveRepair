# DriveRepair 0.3.3b16 — Windows evidence, corrections and hardware QA

Date: 2026-11-19. Input: `gui_debug_20261118T193859.log`, screenshots of the SanDisk SDSSDH3 USB device, and `DriveRepair-main(20261119-124527).zip`.

## What the supplied evidence does and does not show

- The current device inventory identifies a **SanDisk SDSSDH3 500G USB Device**. Sandisk's published `SDSSDH3-500G` Ultra 3D line is a 3D-NAND **SATA SSD**, not a magnetic HDD. This is a model-family match, not confirmation that a USB adapter is passing the original manufacturer's identity faithfully.
- The debug log reports **248 failed scan-read requests** (not necessarily 248 bad sectors) and transitions from SCANNING to REFRESH.
- Progress messages in REFRESH report **5,799,936 rewritten and verified bytes** (5.53 MiB) at the final logged checkpoint. The log does **not** include the complete final structured JSON or independently attest the device's condition.
- The operator's application summary says `Stopped / attention needed (2)` with 248 errors and ~99.96% measured successful reads. In this path exit code 2 may mean `partial_repair_unresolved_data`; raw `exit_code != 0` must not erase the richer backend status.
- At ~100% scanned bytes and ~99.96% covered read regions, neither count indicates file correctness, restored unreadable blocks, nor drive lifespan.
- The read-only native Windows storage property probe may fail when its USB driver denies an IOCTL or stops responding. Drive inventory remains useful; missing device-property details stay **unknown**.

## Changes

1. A Qt-free `repair_presentation` classifier now summarizes the exact backend result. It distinguishes verified rewritten bytes from merely attempted writes, separates independent postwrite verification from in-transaction verification, and reports read-error requests as requests, never sector counts.
2. The status card appears before the evidence map. One progress bar shows planned job stages; an auxiliary phase progress bar is hidden. Guided operations cap interim displayed progress below 100% until postverification and health result processing return.
3. `drive_inspection_text` preserves model, transport, capacity, masked serial suffix and reported sector size even when optional OS inspection fails. It excludes raw serial fields and rejects a stale result for another selected device.
4. The exact SanDisk Ultra 3D `SDSSDH3` model family gets an advisory SSD scan/rescue profile. Contradictory rotational/solid-state evidence becomes unknown. The raw patient-writer path **requires confirmed rotational media** in source and guarded builds. Unknown-health consent no longer establishes media type.

## Acceptance / hardware handoff (not performed here)

- On Windows with PySide6, launch `qt-gui`, select the SSD via USB, inspect the model-family warning and confirm **Targeted HDD repair** is disallowed before a scan. Make an image on separate healthy storage first.
- Select **Details** with a USB adapter that blocks `IOCTL_STORAGE_QUERY_PROPERTY`: the dialog must show known inventory facts and explicitly mark the optional capability probe as unavailable. Test timeout, reconnect, selection switch, and no concurrent inspection during an active repair.
- Using an intentionally damaged *file fixture*, simulate a successful journaled rewrite with unresolved errors and verify the status card is **Partial maintenance — unreadable data remains**, not `Stopped (2)` and not a healthy-drive score.
- With **sacrificial confirmed HDD only**, run short bounded recovery and test independent postwrite digest checks and before/after SMART counters. Do not attempt on the SanDisk SSD. Unexpected repeated read errors or drive resets warrant stopping and rescoring the recovery priority.
- Verify resizing at 100%, 125%, and 150% scaling; keyboard navigation, sidebar shortcut keys and result-first order. Native Qt was not available in the development environment.
- In a guarded repair-beta artifact, confirm that an unknown-USB-medium test cannot be overridden by unknown-health acknowledgements. Confirm legitimate HDD SMART and journal/identity checks still work. Test separate-drive imaging and blocked Windows access behavior.
- Qualify BIOS and UEFI boot on sacrificial USB media separately; an ISO accepted by the writer has not thereby been boot tested.

## Unresolved limits

Physical NAND recovery, dead-sector reconstruction, OS USB driver cancellation and post-repair lifetime cannot be guaranteed by software. Win32 cancellation is best effort when drivers cannot cancel in-flight requests. No native Rust raw I/O implementation was added in this patch. No native PySide6 interaction, Windows raw drive repair, or BIOS/UEFI boots were performed in this environment.

## Primary documentation

- [SanDisk Ultra 3D SSD official product specification](https://www.sandisk.com/products/ssd/internal-ssd/sandisk-ultra-3d-sata-iii-ssd?sku=SDSSDH3-500G-G26)
- [SanDisk SSD endurance reference](https://support-en.sandisk.com/app/answers/detailweb/a_id/49386/~/sandisk-internal-ssd-endurance-and-warranty-periods)
- [Microsoft: cancellation of pending I/O is not guaranteed](https://learn.microsoft.com/en-us/windows/win32/fileio/canceling-pending-i-o-operations)
