# DriveRepair workstation — visual and workflow redesign

**Date:** November 18, 2026  
**Baseline:** `DriveRepair-main(20261118-221359).zip` provided by owner  
**Scope:** Python desktop UI only; no scan, rescue, journaling, or write authorization engine modifications.

## Purpose

Apply the decision-first workbench approach previously used for Repository Detective without making DriveRepair look like a generic vulnerability dashboard. The first screen should answer: **what source am I using, what will the operation do, will it write to the source, what is known, and what should I do next?**

## Changes

- **Persistent workspace sidebar:** Diagnose / Rescue data / experimental Repair, with beta-disabled repair explicitly labeled. Navigation tracks the active operation. Keyboard shortcuts: `Ctrl+1` Diagnose, `Ctrl+2` Rescue, `Ctrl+3` Repair (engineering only), `Ctrl+K` searchable quick switcher, `Ctrl+L` expert log.
- **Persistent action dock:** Start, Stop and actionable readiness checks stay visible while scrolling; no action is staged without a source. Navigation/device changes are disabled while a process is active, preventing misleading retargeting.
- **Progress and coverage:** Planned work progress, current phase, observed successful-read coverage and source-rescue map are separate. The map does not color untested regions as good. Speed graph uses only local, measured throughput samples; no synthetic projections or remote chart service.
- **More useful results:** Readable results, unresolved work and suggested next steps. Copy an explicitly labeled local operator summary; copying is initiated by the user, not auto-uploaded.
- **Image-to-image rescue:** A source image is the only required source; the physical-drive picker is hidden for this operation and its size cannot contaminate the map. Saving to a new destination is still a separate explicit step.
- **Visual system:** Navy/teal palette, compact sidebar, low-noise flat cards, strong keyboard focus, consistent title hierarchy, wrap-safe text, model and serial-suffix descriptions, and a coherent matching palette in legacy Tk.

**No engine repair capability was changed.** Public-beta write restrictions are preserved and remain authoritative in the CLI and packaged policy, not in the Qt button. UI state only gates convenience; the CLI repeats the safety and identity checks.

## Automated evidence

Use `PYTHONPATH=desktop python -m pytest -q desktop/tests` for synthetic regression coverage and `PYTHONPATH=desktop xvfb-run -a python -m pytest -q desktop/tests/test_gui_workflows.py` for Tk clickthrough. The new `test_workstation_ui.py` validates source gating and avoids false health/success statements. Building a public-beta zipapp additionally runs the unittest suite and tests the package entrypoint.

## Manual GUI / accessibility signoff still required

- [ ] On Windows with PySide6, launch `python -m driverepair_desktop qt-gui`; verify there are no widget errors or clipped items at 920×640, 1280×720 and 1920×1080, with Windows display scaling 100%, 125% and 150%.
- [ ] Navigate Sidebar Diagnose/Rescue, Ctrl+1/2/K/L, and Ctrl+3 only in engineering; verify all selected operations match the visible risk impact.
- [ ] Without a device, Start remains unavailable and says why; selecting a device enables read-only diagnostics. On device disconnect, do not infer health or automatically start a write.
- [ ] Select Rescue → Existing image, with **no physical drive** available; choose a real source image and verify Start enables. Cancel destination dialog, then choose a NEW destination on a separate physical disk. Confirm no source modification.
- [ ] Start a synthetic image rescue and verify nonzero throughput and an accurate rescue map. Check that the map does not show a previously selected physical disk's size.
- [ ] During an operation, inspect the phase/overall progress distinction, Stop and sidebar lockout. Confirm stalled I/O displays the observed stall without manufacturing progress.
- [ ] After completion and after an error, use Copy operator summary; confirm it describes a local observation rather than declaring a drive repaired or healthy.
- [ ] Confirm high-contrast readable focus rings and text, keyboard access, no horizontal clipping, scrollable evidence, and accessible tooltips.
- [ ] On a machine without PySide6, run `gui-legacy` and validate that existing Tk workflows still work. The new sidebar is a Qt-workstation feature; Tk received palette alignment, not a complete layout rewrite.
- [ ] Confirm the public-beta `.pyz` refuses all in-place write commands even when supplied by CLI; perform **no** production-disk write test.

## Limitations

No native PySide6 runtime was available in the development sandbox, so this revision has not had a full Qt clickthrough or screenshot comparison. No physical drives, firmware interfaces, exclusive Windows locks, or native repair transactions were exercised. The UI improvements are not a validated neural algorithm or an independent recovery benchmark.
