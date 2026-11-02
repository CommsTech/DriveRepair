# DriveRepair 0.3.3b3 — GUI Workflow Defect & Recovery Verification

**Date:** 2026-11-01  
**Input:** User-uploaded `DriveRepair-main(7).zip`  
**Scope:** Source inspection, GUI workflow reproduction/correction, portable child-process integration, synthetic recovery regression, limited safety review. No patient device read/write was performed.

## Executive finding

**The reported unresponsive buttons were a reproducible, critical GUI defect.** The seven **Start here** buttons passed nested `page` widgets to `ttk.Notebook.select()` rather than the registered notebook `container` widgets. Tk throws `_tkinter.TclError: ... is not managed by ...` but the original UI did not surface that exception. In a virtual GUI I invoked the actual **My external drive is slow or failing** and **My files were accidentally deleted** buttons and reproduced the error and unchanged tab before editing.

**Fixed:** Each named workflow now maps directly to the registered Notebook container. All seven choices navigate correctly, direct tab navigation is intact, and an unexpected Tk callback error now appears in an error dialog and Advanced log.

## Additional fixes

1. **Initial layout:** Idle, empty summary/sector-map panels are hidden so guided choices fit at 1180×820. A **Show recovery dashboard** toggle reveals them manually. The recovery dashboard appears when a job starts; persistent Stop and Advanced controls remain available.
2. **Portable `.pyz` engine startup:** A GUI opened with `python DriveRepair-0.3.3b3.pyz gui` now launches its child recovery engine with the same `.pyz`, not `python -m driverepair_desktop` (which can be unresolvable without separate installation).
3. **Windows live rescue GUI:** The guarded Windows `rescue-external` CLI pathway was implemented previously but hidden by a Linux-only GUI restriction. The GUI exposes it on Windows and Linux, while retaining source read-only opening and source/destination safety checks. **The new GUI connection has not been tested with physical Windows USB hardware.**
4. **Process hygiene:** Child streams are decoded as UTF-8 and their pipes are closed. The poll timer is canceled during ordinary UI shutdown.
5. **Packaging:** The repository packaging script's stale 0.3.3b1 zipapp version was aligned with the new 0.3.3b3 Python package version. CI runs Tk integration tests under Xvfb on Linux, including testing that the portable GUI can launch a recovery job.
6. **Test completion criterion:** A GUI end-to-end test was changed to inspect the committed rescue journal rather than treating a preallocated image's final logical length as completed recovery. Only after `clean_rescue_complete` can it compare full-image SHA-256.

## Validation evidence

| Test/check | Result | Limit |
|---|---|---|
| Bug reproduction on unmodified uploaded GUI | **REPRODUCED** | Real Tk under Linux Xvfb, not Windows |
| All 7 guided Start Here buttons click/navigate to intended pages | **PASS** | Real Tk widgets in virtual display |
| Direct tabs select and drive controls appear after navigation | **PASS** | Simulated empty device inventory |
| Idle dashboard collapse / expansion | **PASS** | Real Tk widgets |
| Quick scan with no selected drive shows input error | **PASS** | Prevents accidental implicit target selection |
| GUI → image recovery engine → persisted journal → SHA-256 exact output | **PASS** | Synthetic regular-file image only |
| Portable `.pyz` GUI → recovery subprocess → exact synthetic output | **PASS** | Linux virtual display; no hardware |
| All Python regression tests | **190 run; 187 passed, 3 skipped** | 3 are platform-specific |
| Portable zipapp and wheel packaging | **PASS** | Not a signed OS-native installer |
| Patch applies against exact `DriveRepair-main(7).zip` source | **PASS** | Original compressed build artifacts excluded |
| Windows laptop clicking and hardware rescue | **NOT TESTED** | Requires actual Windows and a disposable external disk |
| macOS Tk and USB raw-device rescue | **NOT TESTED** | Raw rescue remains unsupported in GUI |
| Physical destructive refresh, power-loss/disconnect behavior, BIOS/UEFI boot | **NOT TESTED** | Remain separate beta release blockers |
| Rust core compilation / native binaries | **NOT TESTED** | This update changes the Python desktop path only |

### Test commands

```bash
cd desktop
# Headless CI/CLI tests
python -m unittest discover -s tests -v
# Real GUI events under a virtual display
xvfb-run -a python -m unittest discover -s tests -p test_gui_workflows.py -v
cd ..
# Package with offline build script
python scripts/build_desktop.py
cd desktop
# Exercise portable GUI's child process and recovery journal
DRIVEREPAIR_SMOKE_PYZ=../dist/DriveRepair-0.3.3b3.pyz \
  xvfb-run -a python -m unittest discover -s tests -p test_gui_workflows.py -v
```

## Operator walkthrough (Windows)

1. Close the previous DriveRepair GUI; do not terminate an active rescue without preserving its image and recovery map.
2. Open the updated build: `python DriveRepair-0.3.3b3.pyz gui`, with Python 3.10+ and Tk installed, or install the matching wheel and run `driverepair-gui`.
3. Click **My external drive is slow or failing**. The **Diagnose / Rescue** tab should open. If the disk list is empty, click **Refresh inventory**.
4. Check the disk's **model, capacity, bus, masked serial and identity hint** before selecting its row. A USB bridge can mask disk metadata; do not assume the first row is the intended patient.
5. **Quick scan** is read-only diagnosis, not a repair. For image rescue, choose an output file on a separate healthy destination, ensure free space, and use **Rescue (Linux/Windows)** with the user risk acknowledgment. Windows physical rescue requires elevated permission and validated destination separation.
6. For interrupted rescues, use **Resume rescue** with the original image and its persisted map. Do not delete that map. The destination image may have its full logical length long before the data is fully rescued.
7. During an operation the dashboard appears; observe bytes processed, unreadable gaps, speed, ETA and destination capacity. Open **Advanced details** only for diagnostics.

## Release decision

**Desktop GUI navigation: fixed and proven in Linux virtual-display and synthetic tests.**  
**General physical-drive beta release: NOT YET QUALIFIED.** An operator should still conduct Windows GUI clickthrough, actual USB dock inventory tests, read-only scanning, paused/resumed imaging and fault injection on disposable drives. This work does not certify the efficacy of sector rejuvenation, correctness of recovered file bytes without trusted checksums, or physical-drive writes.

The source archive is stripped of compiled caches and prior local `target/` artifacts; this does not alter the project's Rust or experimental bootloader source. Source changes are provided as a separate Git patch for Cursor/Gitea review.
