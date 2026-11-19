# DriveRepair v0.3.3b18 — QA handoff

Date: 2026-11-19. Source baseline: `DriveRepair-main(20261119-134405).zip`.

## Reproduced from operator evidence

1. The root README led with dated change notes, not installation or workflows.
2. The USB flash dialog had a target selected and the exact `ERASE windows:PhysicalDrive4` text entered, but the independent destructive-data-loss checkbox remained unchecked. The disabled button was **expected**, while the absence of an explicit explanation was a UX defect.
3. A Seagate ST1000LM048 is recognized by model family, but that is not proof that the current USB bridge presents a rotational HDD suitable for in-place rewrites. The guarded UI declines repair when SMART rotation, health or serial identity is not verified. The earlier read-only scans alone do not justify a write.
4. Windows HealthStatus alone does not certify SMART or medium identity. An unavailable `smartctl` installation or a bridge that does not pass SAT will still block repair. `WinError 5` and blocked kernel I/O remain OS/hardware qualification issues.

## Implemented

- New top-level product README, shorter desktop README and portable boot-kit README. Previous long README text is archived in `docs/README_ENGINEERING_HISTORY.md` and `docs/README_DESKTOP_ENGINEERING_HISTORY.md`.
- One bounded read-only ATA SAT `smartctl -d sat` probe after default USB smartctl results are invalid or have an open/command error; does not retry a hung default probe or overwrite reported SMART media failure. Requires ATA protocol and numeric rotation evidence. **Not** a method for bypassing bridge limitations.
- `Check HDD eligibility` in the Qt repair workspace, with explicit result text and no writes. The engine still enforces all identity, health, locks, risk and independent-journal requirements.
- USB creator shows *which* step is missing before flashing: disposable target, exact typed `ERASE` string, or separate data-loss acknowledgement. It does **not** auto-check consent. Added direct navigation to Rescue Data for users who meant to **image a patient disk** instead of flashing boot media.

## Synthetic test results

See the final tester log for exact count. Added `desktop/tests/test_b18_smart_usb_readiness.py` with tests for SAT fallback, a default query with invalid JSON or open failure, refusing non-ATA response, preserving known SMART failure, not retrying timed-out first I/O, and explicit flash consent logic. No tests write to real USB devices.

## Windows hardware QA: must be performed by a trusted Windows-enabled agent

| Test | Expected result | Evidence to collect |
| --- | --- | --- |
| Qt on Windows 10/11, default scaling and 125%/150% | `Check HDD eligibility` visible and usable in Repair workspace, status legible at small window sizes | Screenshots before/after probe |
| Flash dialog, source ISO, target selected, erase text typed, checkbox unchecked | Flash button disabled; status explicitly says **Step 3/3** is missing | Screenshot of status and unchecked checkbox |
| Check consent box | Flash button becomes enabled only after selected target, exact text and acknowledgement | Screenshot (do **not** click unless disposable USB) |
| Click `I want to image a disk instead` | Flash dialog closes and user moves to Rescue Data; no writes | Screenshot and list of active processes |
| USB flash on disposable stick with verified image | All safety/lock/identity gates pass; full image readback matches; BIOS/UEFI boot separately assessed | Redacted worker log, byte hash, BIOS/UEFI boot outcomes |
| Seagate ST1000LM048 through SAT-capable USB bridge with smartmontools | SMART rotation/health becomes visible, Qt readiness updates, physical repair allowed only if independent engine gates pass | Redacted `smartctl -j -a` and `smartctl -j -a -d sat` results (no full serial), Qt status |
| Same HDD through bridge without SAT | Clear reason repair remains blocked, Rescue Data available | Redacted CLI stderr and Qt status |
| SSD / NVMe / removable flash selected | HDD-specific repair remains ineligible, no raw write attempted | Qt screenshot, engine result, device type |
| Physically failing HDD or critical SMART failures | Do not force repair. Minimize further reads and use lab/sacrificial-only testing | Rescue status and redacted SMART trends |
| `WinError 5`, mounted volumes, changing serial/fingerprint | Operation fails safely without writes; never bypass OS locks | Redacted error log |

**Do not test raw repair on valuable data.** Synthetic tests do not prove restored drive life, repair success on failing hardware or that blocked kernel I/O can be canceled.

## Remaining engineering gaps

- Native PySide6 clickthrough not verified in the build environment.
- Physical Windows HDD writes, actual USB flash and BIOS/UEFI boot not tested here.
- A qualified live ISO is not included in the source archive. A built ISO's header markers do not independently prove bootability.
- A documented manufacturer-model compatibility database, hardware-backed retention/lifetime validation and a native Rust raw I/O implementation remain future work.
