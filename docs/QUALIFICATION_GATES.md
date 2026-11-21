# DriveRepair qualification and agent handoff — b36

## What automatic CI can prove

**Required Ubuntu `.gitea/workflows/ci.yml`:** Python tests, source packaging,
Rust checks, lint/security checks and release-hygiene metadata. Synthetic
storage tests use ordinary files, not physical media. A green Ubuntu pipeline
is **not** a public-binary qualification.

**Opt-in `.gitea/workflows/qualification.yml`:** Runs with manual
`workflow_dispatch`. Requires a Windows-capable Actions runner for native
PySide6 widget tests and a privileged Ubuntu runner for Debian live-build plus
QEMU/OVMF. The workflow is optional, rather than making existing Ubuntu CI
silently fail on a missing Windows runner. If a runner is absent or a job never
ran, its result is **NOT_PROVEN**, not PASS.

The ISO job builds an ordinary ISO and calls:

```sh
python scripts/smoke_live_iso.py \
  --iso /path/DriveRepair-Live-amd64-UNVERIFIED.iso \
  --output /path/to/qa-evidence --timeout-seconds 360
```

The VM boots with only a read-only optical ISO drive and a disposable UEFI
variable image; no hard disk or network devices are attached. The guest sends
`DRIVEREPAIR_LIVE_READY:GUI_STARTED` over QEMU serial only after LightDM and
the DriveRepair GUI process exist. The command records per-firmware PASS/FAIL
and the ISO SHA-256 in `vm_boot_evidence.json`. **This confirms neither UEFI
Secure Boot nor that the HP laptop can boot or actually use the interface.**
A captured marker is not a substitute for manually inspecting the boot menu
and clicking the application.

The ISO recipe is duplicated in:
`desktop/driverepair_desktop/boot_resources/build_live_iso.sh` and
`scripts/build_live_iso.sh`, because the portable app exports its own kit.
Keep these copies byte-identical. Both BIOS and EFI bootloader source menus
must reference the same DriveRepair titles; still verify the finished EFI
image by booting it.

## Hardware gates that automation must not fake

Follow `docs/QA_2026-11-20_HP_BOOT_WINDOWS_DOCK.md` on **disposable media**.
Test normal and compatibility boot on the HP laptop, autologin, correct GUI
start, and correct boot menu; test SSD-specific HDD denial. On Windows,
run the native Qt tests and the read-only USB SMART compatibility diagnostic:

```powershell
# External disks only; elevated PowerShell for ordinary read-only scan.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\qa_readonly_triage.ps1 `
  -Devices windows:PhysicalDrive2 -OutputDir C:\temp\driverepair-qa
```

`*.smart.json` reports only selected diagnostic fields, the `/dev/pdN` alias
and errors; full SMART serials and raw stdout/stderr are deliberately omitted.
An unknown or unreadable report **cannot** authorize on-device writes.
A dedicated manual test using a backed-up, disposable rotational HDD is
needed to verify USB-dock locking, journal and readback behavior. Disconnects,
wrong identity, missing rights and cancellation should fail closed.

## Evidence file format for promotion

`python scripts/check_release_readiness.py --help` documents arguments.
Supply a JSON object, for the **exact distributable artifact** under review:

```json
{
  "version": "0.3.3b36",
  "source_commit": "full-git-commit-id-for-that-build",
  "artifact_sha256": "64-char-hex-sha256-of-exact-iso-or-release-file",
  "checks": {
    "bios_vm": {"status": "PASS", "evidence": "VM job URL and console/log checksum"},
    "uefi_vm": {"status": "PASS", "evidence": "UEFI VM job URL and console/log checksum"},
    "native_windows_qt": {"status": "PASS", "evidence": "Windows job URL and test output"},
    "usb_dock_hw": {"status": "PASS", "evidence": "reviewed sacrificial HDD QA log"},
    "hp_laptop_hw": {"status": "PASS", "evidence": "HP laptop boots & UI test record"}
  }
}
```

The gate fails if a required field is missing, does not match, or is not PASS.
This is an **evidence consistency check**, not cryptographic attestation; an
independent reviewer must confirm authenticity, safety, and hardware identity.
Do not mark missing tests PASS just to satisfy a script. Use NOT_PROVEN / FAIL
until real evidence exists. Do not publicize as hardware-qualified otherwise.

## Source handoff

1. Run `python scripts/check_release_hygiene.py` and the normal test suite.
2. Build a clean ZIP OUTSIDE the checkout:
   `python scripts/create_clean_source_archive.py --output /tmp/driverepair-clean-source.zip`.
3. Generate a patch from the exact baseline commit: `git diff --binary BASE..HEAD > improvements.patch`.
4. Apply the patch in Gitea against the matching source revision, not a
   differently labeled b35 archive; review SHA-256 and CI before merging.
