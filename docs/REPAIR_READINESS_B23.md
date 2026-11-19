# DriveRepair 0.3.3b23 — Windows USB SMART and repair-readiness QA

This build is for **lab qualification**, not production recovery. The latest operator screenshot shows an ST1000LM048 model identified as SMR via a vendor/model database, but the repair gate lacks independent rotational/SMART evidence from the USB path. The uploaded GUI debug log only shows session initialization; it contains **no SMART result or attempted repair**.

## What changed

The Qt HDD workspace provides a **single next action** with a disabled physical-write Start until media and health evidence satisfy the independent safety policy. Without smartctl it offers a consent-based setup path; with smartctl it launches a bounded, read-only identification probe; if the protocol proves non-HDD media or remains unverified, it offers rescue to an image. The local log now retains the actual probe error. A mismatched returned disk fingerprint is rejected; an ambiguous USB serial or unrelated bridge ID must never authorize a write.

The SMART probe can retry an auto query whose ATA rotation field appeared usable but whose smartctl process still returned a command error. It does **not** override an existing media-failure warning, issue self-tests, or write patient bytes.

## Lab validation checklist

1. On Windows, test **HDD maintenance** with no smartctl. Confirm the action is **Enable SMART identification**, that approval is required to install a tool, and Start stays disabled. Check source drive has not been modified.
2. With a verified smartctl installed, select ST1000LM048 through a SAT-capable dock and press **Check drive SMART and identity**. Verify raw JSON separately with the official `smartctl --json --all -d sat \\.\PhysicalDriveN` (replace `N` and use an authorized lab machine). Never assume success based on model text.
3. With a USB bridge that hides ATA rotation or fails pass-through, confirm the exact failure is shown and **Rescue data to an image** is available. Do not bypass the lock, journal, identity or SMART gates.
4. Reconnect the dock to a different USB port/PhysicalDrive number, or replace it with a different disk; verify the old SMART result cannot authorize the new disk.
5. Select an SSD/NVMe or flash stick; confirm the HDD write button remains disabled even if a model name resembles a known HDD.
6. On a **sacrificial HDD only**, after an external full backup and health/identity approval, attempt a small guided rewrite batch. Validate exclusive Windows access, durable journal location on different physical media, post-write digest verification, no unexpected adjacent writes, and health counters before/after. Repeat with forced error/disconnect in a controlled bench.
7. With PySide6 available, test the Qt flow at Windows 125%, 150%, 200% scaling and 1366×768 and 1920×1080 resolutions, including screen-reader labels, next-action control and long SMART error strings.
8. Confirm `gui_debug` captures SMART rejection text without storing a full serial number, credentials, or patient file contents. Disable debug logging for ordinary users.

## Not verified in this environment

No actual Windows USB bridge, Qt visual clickthrough, physical media write, firmware reaction, or bootable-USB BIOS/UEFI start was tested.  Synthetic SMART tests do not prove that drive reliability improves after maintenance. The release contains no trained neural reconstruction model and no bundled upstream Windows `smartctl.exe` binary.
