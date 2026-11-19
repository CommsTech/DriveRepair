# DriveRepair 0.3.3b17 — USB SMART preflight and GUI QA handoff

## Evidence from operator screenshots

- Seagate `ST1000LM048` via USB shows manufacturer-model **SMR** classification but physical-write permission blocked due to missing independently measured media/SMART evidence. The screen previously still allowed **Start authorized repair** in engineering mode, then returned exit code 1 without a scan. This was a *preflight UX defect*; the model-name classification and the write restriction are two different claims.
- SanDisk `SDSSDH3` is a published SSD family; it remains **not eligible** for HDD-specific rewrites. Removable flash and unknown media likewise remain image-first.
- USB creator has a selected ISO and sacrificial USB target, but the ISO header check proves neither bootability nor a safe host/disk mapping. Typed `ERASE <disk-id>` plus the separate unchecked data-loss confirmation remain mandatory.

## Implemented

1. Qt checks the same `advise()`-based physical media decision for **all** release channels before opening a care subprocess. A missing SMART snapshot is a reason to scan/rescue, never a write pass. Core CLI gates are unchanged and authoritative.
2. The repair pane exposes a direct **Rescue to image instead** action if repair preflight fails. Status now calls initial silence "preflight" rather than a device read stall and does not leave "Waiting on drive" as a completed job metric.
3. A single bounded SATA pass-through SMART probe (`-d sat`, ATA only) is attempted for external USB drives when automatic smartctl cannot establish rotation rate. It only accepts a real rotation-rate declaration with a successful command/open result; unsupported bridges remain unknown.
4. No dummy health gauge until a score exists; no manufacturer hours control until actual power-on-hours evidence exists. Flash wizard explicitly labels the ISO **boot unverified**.

## Mandatory Windows hardware handoff (DO NOT use valuable data)

- Install and locate a current smartmontools build; compare automatic SMART versus `-d sat` read-only output on a sacrificial Seagate ST1000LM048 through the actual dock. Record safe serial/rotation/health metadata *without full serials*. A bridge that does not pass SAT remains write-ineligible.
- On a real SSD (including SDSSDH3) and a USB flash stick, verify that the HDD repair Start button is **disabled before launch** with a Rescue action. Confirm no physical open-for-write or scan job started. The CLI must independently refuse when invoked directly.
- On a sacrificial rotational disk that reports SMART, confirm the UI permits the authorization wizard **only** once SMART media, lock, identity and journal requirements can be met. Check actual journal/verification before declaring a repair. A click alone proves nothing.
- Run through failed SMART, OS metadata timeouts, drive change, USB unplug, Windows kernel-blocked read, and USB bridge serial duplicates. Validate the GUI never reports full repair or healthy data without independent evidence.
- Visually test Qt in Windows at 100/125/150/200% DPI and smaller windows, screen-reader focus and keyboard-only navigation. The native Qt window was not executed in the code review environment.
- Test USB flash only with an expendable stick and a **separately qualified** DriveRepair live ISO, then BIOS/UEFI boot and read-only patient behavior. No USB flash or boot occurred in this change.

## Required output from hardware agent

Capture selected drive/model/bus/sector, SMART probe result source (auto or SAT), media confidence, redacted identity hint, reason for repair readiness decision, command exit status, journal location (redacted), postwrite verification, whether any source write occurred, and a screenshot of each blocked/unblocked state. Mark unknowns explicitly. Do not upload raw SMART serials or private recovered data.

## Source references

- Seagate BarraCuda 2.5 DS1907.4-2507US, table: ST1000LM048, 5400 RPM, SMR.
- smartmontools `smartctl(8)` device type / `-d sat` documentation. USB SAT translation depends on enclosure/controller support.
